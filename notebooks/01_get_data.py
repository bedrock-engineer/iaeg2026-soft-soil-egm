# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "bromodels==0.0.1",
#     "folium==0.20.0",
#     "geopandas==1.2.0",
#     "mapbox-vector-tile==2.2.0",
#     "marimo",
#     "marimo-lens==0.2.4",
#     "mercantile==1.2.1",
#     "netcdf4",
#     "pmtiles==3.8.1",
#     "polars",
#     "pyarrow",
#     "pygef==0.13.0",
#     "pyproj",
#     "shapely==2.2.0",
#     "xarray",
#     "xmltodict",
# ]
# ///

# PROTOTYPE: throwaway notebook for the ticket
# "Which geological units does the model distinguish?" (issue #5).

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def intro(mo):
    mo.md("""
    # Download model data
    Start from the approximate footprint from the model's Floors elements. Adjust the buffer, inspect the touched GeoTOP columns and BRO locations, then download the selected data. All files under `data/` are downloaded, so can be ignored by Git.
    """)
    return


@app.cell(hide_code=True)
def imports():
    import gzip
    import hashlib
    import html
    import io
    import json
    import math
    from functools import lru_cache
    from pathlib import Path
    from urllib.request import Request, urlopen
    import bromodels
    import folium
    import geopandas as gpd
    import mapbox_vector_tile
    import marimo as mo
    import mercantile
    import polars as pl
    import pyproj
    import shapely
    import xarray as xr
    from marimo_lens import Lens
    from pmtiles.reader import Reader
    from pygef import read_cpt

    return (
        Lens,
        Path,
        Reader,
        Request,
        bromodels,
        folium,
        gpd,
        gzip,
        hashlib,
        html,
        json,
        lru_cache,
        mapbox_vector_tile,
        math,
        mercantile,
        mo,
        pl,
        pyproj,
        read_cpt,
        shapely,
        urlopen,
        xr,
    )


@app.cell(hide_code=True)
def building_footprint(BIM_URL, gpd, pl):
    floor_elements = pl.scan_parquet(BIM_URL).filter(pl.col("class").cast(pl.String) == "Floors").select("geog").collect()
    if floor_elements.is_empty():
        raise ValueError("No Floors elements found in the R2 model")
    building_footprint_geog = gpd.GeoSeries.from_wkb(floor_elements["geog"].to_numpy(), crs="OGC:CRS84").force_2d().make_valid().union_all()
    # Compare areas in metres, not longitude/latitude degrees.
    _parts = gpd.GeoSeries([building_footprint_geog], crs="OGC:CRS84").to_crs(28992).explode(index_parts=False)
    _polygons = [part for part in _parts if part.geom_type == "Polygon" and not part.is_empty]
    if not _polygons:
        raise ValueError("The combined BIM model contains no polygon footprint")
    building_footprint = gpd.GeoDataFrame({"layer": ["Approximate footprint from Floors"]}, geometry=[max(_polygons, key=lambda part: part.area)], crs=28992).to_crs("OGC:CRS84")
    footprint_rd = building_footprint.to_crs(28992).geometry.iloc[0]
    return building_footprint, footprint_rd


@app.cell(hide_code=True)
def selection_functions(
    BRO_LOCATIONS_URL,
    Reader,
    Request,
    gpd,
    gzip,
    lru_cache,
    mapbox_vector_tile,
    math,
    mercantile,
    pyproj,
    shapely,
    urlopen,
):
    def touched_geotop_columns(area):
        """GeoTOP coordinates denote southwest corners of 100 m cells."""
        xmin, ymin, xmax, ymax = area.bounds
        rows = []
        for y in range(math.floor(ymin / 100) * 100 - 100, math.floor(ymax / 100) * 100 + 101, 100):
            for x in range(math.floor(xmin / 100) * 100 - 100, math.floor(xmax / 100) * 100 + 101, 100):
                footprint = shapely.box(x, y, x + 100, y + 100)
                if footprint.intersects(area):
                    rows.append({"geotop_x": x, "geotop_y": y, "geometry": footprint})
        return gpd.GeoDataFrame(rows, crs=28992)

    @lru_cache(maxsize=512)
    def pmtiles_bytes(offset, length):
        request = Request(BRO_LOCATIONS_URL, headers={"Range": f"bytes={offset}-{offset + length - 1}"})
        with urlopen(request, timeout=60) as response:
            if response.status != 206:
                raise RuntimeError("PMTiles host did not honor the HTTP Range request")
            data = response.read()
        if len(data) != length:
            raise RuntimeError("Incomplete PMTiles range response")
        return data

    @lru_cache(maxsize=64)
    def bro_tile_records(z, x, y):
        reader = Reader(pmtiles_bytes)
        raw = reader.get(z, x, y)
        if raw is None:
            return []
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        decoded = mapbox_vector_tile.decode(raw)
        bounds = mercantile.xy_bounds(x, y, z)
        to_rd = pyproj.Transformer.from_crs(3857, 28992, always_xy=True)
        rows = []
        for kind in ("cpt", "bhrgt"):
            layer = decoded.get(kind, {})
            extent = layer.get("extent", 4096)
            for feature in layer.get("features", []):
                props = feature["properties"]
                if "point_count" in props or not props.get("bro_id"):
                    continue
                if feature["geometry"]["type"] != "Point":
                    continue
                tx, ty = feature["geometry"]["coordinates"]
                # Decoder returns y-up tile coordinates by default.
                mx = bounds.left + tx / extent * (bounds.right - bounds.left)
                my = bounds.bottom + ty / extent * (bounds.top - bounds.bottom)
                rx, ry = to_rd.transform(mx, my)
                rows.append({**props, "kind": kind, "geometry": shapely.Point(rx, ry)})
        return rows

    def selected_bro_locations(area):
        bbox = gpd.GeoSeries([area], crs=28992).to_crs(4326).total_bounds
        header = Reader(pmtiles_bytes).header()
        zoom = header["max_zoom"]
        rows = {}
        for tile in mercantile.tiles(*bbox, zooms=zoom):
            for row in bro_tile_records(tile.z, tile.x, tile.y):
                if area.covers(row["geometry"]):
                    rows[(row["kind"], row["bro_id"])] = row
        if not rows:
            return gpd.GeoDataFrame({"bro_id": [], "kind": []}, geometry=[], crs=28992)
        return gpd.GeoDataFrame(list(rows.values()), crs=28992)

    return selected_bro_locations, touched_geotop_columns


@app.cell(hide_code=True)
def selection(
    buffer_distance,
    footprint_rd,
    mo,
    selected_bro_locations,
    touched_geotop_columns,
):
    buffer_rd = footprint_rd.buffer(buffer_distance.value)
    geotop_columns = touched_geotop_columns(buffer_rd)
    selection_rd = geotop_columns.geometry.union_all()
    with mo.status.spinner("Reading selected CPT and BHR-GT locations from PMTiles…"):
        selected_locations = selected_bro_locations(selection_rd)
    selected_cpt_ids = sorted(selected_locations.loc[selected_locations["kind"] == "cpt", "bro_id"].tolist())
    selected_bhrgt_ids = sorted(selected_locations.loc[selected_locations["kind"] == "bhrgt", "bro_id"].tolist())
    mo.md(f"**{len(geotop_columns)} GeoTOP columns · {len(selected_cpt_ids)} CPTs · {len(selected_bhrgt_ids)} geotechnical boreholes**. Selected against the exact cell union, including its boundary. Locations in vector tiles have metre-scale quantization; downloaded profile coordinates are checked again.")
    return (
        buffer_rd,
        geotop_columns,
        selected_bhrgt_ids,
        selected_cpt_ids,
        selected_locations,
        selection_rd,
    )


@app.cell(hide_code=True)
def settings(Path, mo):
    DATA_DIR = Path(mo.notebook_dir()).parent / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BIM_URL = "https://r2.eu.bedrock.engineer/bimpolars/rvt-advanced-sample/rvt-advanced-sample-combined-arch-str-bdf.parquet"
    BRO_LOCATIONS_URL = "https://r2.eu.bedrock.engineer/bro_locations.pmtiles"
    buffer_distance = mo.ui.slider(start=0, stop=1000, step=25, value=200, label="Buffer around building footprint (m)", show_value=True)
    MODEL_BOTTOM_NAP = -50
    buffer_distance
    return (
        BIM_URL,
        BRO_LOCATIONS_URL,
        DATA_DIR,
        MODEL_BOTTOM_NAP,
        buffer_distance,
    )


@app.cell(hide_code=True)
def selection_map(
    buffer_rd,
    building_footprint,
    folium,
    geotop_columns,
    gpd,
    html,
    mo,
    selected_locations,
):
    _centre = building_footprint.geometry.iloc[0].centroid
    selection_map = folium.Map(location=[_centre.y, _centre.x], zoom_start=16, tiles=None, height=540)
    folium.TileLayer(tiles="https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg", attr="Kadaster / PDOK", name="Aerial photo", max_zoom=19).add_to(selection_map)
    folium.TileLayer("OpenStreetMap").add_to(selection_map)
    folium.GeoJson(building_footprint.to_json(), name="Building footprint", style_function=lambda _: {"color": "#dc2626", "weight": 2, "fillOpacity": 0.25}).add_to(selection_map)
    folium.GeoJson(gpd.GeoSeries([buffer_rd], crs=28992).to_crs(4326).to_json(), name="Buffer", style_function=lambda _: {"color": "#f59e0b", "weight": 2, "fillOpacity": 0.1}).add_to(selection_map)
    folium.GeoJson(geotop_columns.to_crs(4326).to_json(), name="Touched GeoTOP columns", style_function=lambda _: {"color": "#ffffff", "weight": 1.5, "fillOpacity": 0.05}, tooltip=folium.GeoJsonTooltip(fields=["geotop_x", "geotop_y"])).add_to(selection_map)
    for _kind, _label, _color in [("cpt", "CPTs", "#7c3aed"), ("bhrgt", "Geotechnical boreholes", "#ea580c")]:
        _group = folium.FeatureGroup(name=_label).add_to(selection_map)
        for _, _row in selected_locations[selected_locations["kind"] == _kind].to_crs(4326).iterrows():
            folium.CircleMarker([_row.geometry.y, _row.geometry.x], radius=4, color=_color, fill=True, fill_opacity=0.9, tooltip=html.escape(str(_row.bro_id))).add_to(_group)
    folium.LayerControl().add_to(selection_map)
    _bbox = geotop_columns.to_crs(4326).total_bounds
    selection_map.fit_bounds([[_bbox[1], _bbox[0]], [_bbox[3], _bbox[2]]])
    mo.iframe(selection_map.get_root().render().replace("</head>", "<style>html,body{height:540px!important;min-height:540px!important;}</style></head>"), height="560px")
    return


@app.cell(hide_code=True)
def download_controls(mo):
    download_selected = mo.ui.run_button(label="Download selected data")
    mo.vstack([download_selected, mo.md("Fetches GeoTOP voxel values and BRO source XMLs into the local, Git-ignored `data/` folder. Moving the slider only updates the preview.")])
    return (download_selected,)


@app.cell(hide_code=True)
def download_functions(
    BIM_URL,
    BRO_LOCATIONS_URL,
    DATA_DIR,
    bromodels,
    hashlib,
    json,
    mo,
    pl,
    read_cpt,
    shapely,
    urlopen,
    xr,
):
    def download_selection(columns, area, cpt_ids, borehole_ids, bottom, buffer_m):
        key = hashlib.sha256(json.dumps({"cells": sorted(zip(columns.geotop_x.tolist(), columns.geotop_y.tolist())), "bottom": bottom, "cpts": cpt_ids, "bhrgt": borehole_ids, "bim_url": BIM_URL, "locations_url": BRO_LOCATIONS_URL}, sort_keys=True).encode()).hexdigest()[:16]
        target = DATA_DIR / "selections" / key
        target.mkdir(parents=True, exist_ok=True)
        xml_dir = DATA_DIR / "cpt_xml"
        borehole_dir = DATA_DIR / "bhrgt_xml"
        xml_dir.mkdir(exist_ok=True)
        borehole_dir.mkdir(exist_ok=True)
        netcdf = target / "geotop.nc"
        if not netcdf.exists():
            west, south, east, north = area.bounds
            raw = bromodels.GTM.GeoTop.GeoTopDomain(west=west, south=south, east=east, north=north, bottom=bottom)
            raw = raw[["strat", "lithok"]]
            selected_xy = set(zip(columns.geotop_x, columns.geotop_y))
            mask = xr.DataArray([[ (int(x), int(y)) in selected_xy for x in raw.x.values] for y in raw.y.values], coords={"y": raw.y, "x": raw.x}, dims=("y", "x"))
            raw.where(mask).dropna("x", how="all").dropna("y", how="all").to_netcdf(netcdf)
        frames, outside = [], []
        for bro_id in mo.status.progress_bar(cpt_ids, title="Downloading CPT profiles"):
            path = xml_dir / f"{bro_id}.xml"
            if not path.exists():
                with urlopen(f"https://publiek.broservices.nl/sr/cpt/v1/objects/{bro_id}", timeout=60) as response:
                    path.write_bytes(response.read())
            cpt = read_cpt(path)
            x, y = cpt.delivered_location.x, cpt.delivered_location.y
            if not area.covers(shapely.Point(x, y)):
                outside.append(bro_id)
                continue
            data = cpt.data
            optional = lambda column, alias: pl.col(column).alias(alias) if column in data.columns else pl.lit(None, dtype=pl.Float64).alias(alias)
            rf = "frictionRatio" if "frictionRatio" in data.columns else "frictionRatioComputed"
            frames.append(data.select(pl.lit(bro_id).alias("bro_id"), pl.lit(x).alias("x"), pl.lit(y).alias("y"), pl.lit(str(cpt.research_report_date)).alias("report_date"), pl.lit(str(cpt.cpt_standard)).alias("cpt_standard"), pl.col("depthOffset").alias("z"), pl.col("coneResistance").alias("qc"), optional("localFriction", "fs"), optional(rf, "rf"), optional("porePressureU2", "u2")))
        cpts = pl.concat(frames, how="vertical_relaxed").filter(pl.col("qc") > 0) if frames else pl.DataFrame(schema={"bro_id": pl.String, "x": pl.Float64, "y": pl.Float64, "report_date": pl.String, "cpt_standard": pl.String, "z": pl.Float64, "qc": pl.Float64, "fs": pl.Float64, "rf": pl.Float64, "u2": pl.Float64})
        cpts.write_parquet(target / "cpts.parquet")
        for bro_id in mo.status.progress_bar(borehole_ids, title="Downloading BHR-GT records"):
            path = borehole_dir / f"{bro_id}.xml"
            if not path.exists():
                with urlopen(f"https://publiek.broservices.nl/sr/bhrgt/v2/objects/{bro_id}", timeout=60) as response:
                    path.write_bytes(response.read())
        columns.to_file(target / "geotop_columns.geojson", driver="GeoJSON")
        manifest = {"selection_id": key, "buffer_m": buffer_m, "bottom_nap": bottom, "bim_url": BIM_URL, "bro_locations_url": BRO_LOCATIONS_URL, "cpt_ids": cpt_ids, "bhrgt_ids": borehole_ids, "profile_locations_outside_selection": outside}
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        # Publish standard notebook inputs only after all downloads succeed.
        with xr.open_dataset(netcdf) as dataset:
            dataset.load().to_netcdf(DATA_DIR / "geotop.nc")
        cpts.write_parquet(DATA_DIR / "cpts.parquet")
        (DATA_DIR / "selection.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    return (download_selection,)


@app.cell(hide_code=True)
def download(
    DATA_DIR,
    MODEL_BOTTOM_NAP,
    buffer_distance,
    download_selected,
    download_selection,
    geotop_columns,
    mo,
    selected_bhrgt_ids,
    selected_cpt_ids,
    selection_rd,
):
    mo.stop(not download_selected.value, mo.md("Select an area above, then press **Download selected data**."))
    with mo.status.spinner("Downloading selected model data…"):
        download_manifest = download_selection(geotop_columns, selection_rd, selected_cpt_ids, selected_bhrgt_ids, MODEL_BOTTOM_NAP, buffer_distance.value)
    mo.md(f"Saved selection **{download_manifest['selection_id']}** under `{DATA_DIR}`. {len(download_manifest['profile_locations_outside_selection'])} CPTs were excluded after checking their original coordinates.")
    return


@app.cell(hide_code=True)
def lens(Lens):
    lens = Lens()
    lens
    return


if __name__ == "__main__":
    app.run()
