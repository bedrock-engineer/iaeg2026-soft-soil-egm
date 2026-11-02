# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "bimpolars",
#     "bromodels==0.0.1",
#     "folium==0.20.0",
#     "geopandas==1.2.0",
#     "marimo",
#     "marimo-lens==0.2.4",
#     "netcdf4",
#     "numpy>=2",
#     "polars",
#     "pyarrow",
#     "pyproj==3.8.0",
#     "shapely==2.2.0",
#     "specklewidgets",
#     "xarray",
# ]
#
# [tool.uv.sources]
# bimpolars = { git = "https://github.com/bedrock-engineer/bimpolars" }
# specklewidgets = { git = "https://github.com/bedrock-engineer/specklestuff" }
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Download model data
    Start from the approximate footprint of the model's Floors elements. Adjust the buffer, inspect the touched GeoTOP columns and the BRO's CPTs and geotechnical boreholes in them, then download the selected data. Everything under `data/` is downloaded, so Git ignores it.
    """)
    return


@app.cell(hide_code=True)
def _():
    import io
    import json
    import xml.etree.ElementTree as ET
    from datetime import date
    from pathlib import Path
    from urllib.request import Request, urlopen

    import bimpolars as bpl
    import bromodels
    import folium
    import geopandas as gpd
    import marimo as mo
    import numpy as np
    import polars as pl
    import pyproj
    import shapely
    import xarray as xr
    from marimo_lens import Lens
    from specklewidgets import GeoSpeckleViewer
    from specklewidgets.geo import osm_ground_map, pdok_3d_buildings

    # RD New + NAP to WGS 84 follows RDNAPTRANS2018 only with the NSGI grids, which PROJ fetches
    pyproj.network.set_network_enabled(True)
    return (
        ET,
        GeoSpeckleViewer,
        Lens,
        Path,
        Request,
        bpl,
        bromodels,
        date,
        folium,
        gpd,
        io,
        json,
        mo,
        np,
        pdok_3d_buildings,
        pl,
        shapely,
        urlopen,
        xr,
    )


@app.cell(hide_code=True)
def lens(Lens):
    # marimo-lens: select a region of any output and add a note for the notebook agent
    lens = Lens()
    lens
    return


@app.cell(hide_code=True)
def settings(Path, mo):
    DATA_DIR = Path(mo.notebook_dir()).parent / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BIM_URL = "https://r2.eu.bedrock.engineer/bimpolars/rvt-advanced-sample/rvt-advanced-sample-combined-arch-str-bdf.parquet"
    MODEL_BOTTOM_NAP = -50
    buffer_distance = mo.ui.slider(
        start=0,
        stop=500,
        step=25,
        value=200,
        include_input=True,
        label="Buffer around building footprint (m)",
    )
    buffer_distance
    return BIM_URL, DATA_DIR, MODEL_BOTTOM_NAP, buffer_distance


@app.cell(hide_code=True)
def building_footprint(BIM_URL, gpd, pl, shapely):
    _floors = pl.scan_parquet(BIM_URL).filter(pl.col("class").cast(pl.String) == "Floors").select("geog").collect()
    # The building's footprint: the largest polygon of the union of its Floors, in RD New metres
    _union = gpd.GeoSeries.from_wkb(_floors["geog"].to_numpy(), crs="OGC:CRS84").force_2d().make_valid().to_crs(28992).union_all()
    footprint_rd = max(
        (_part for _part in shapely.get_parts(_union) if _part.geom_type == "Polygon"),
        key=lambda _part: _part.area,
    )
    return (footprint_rd,)


@app.cell(hide_code=True)
def selection_functions(
    ET,
    Request,
    date,
    gpd,
    io,
    json,
    pl,
    shapely,
    urlopen,
):
    def geotop_cells(x, y):
        """The 100 m GeoTOP columns as boxes: GeoTOP's x and y (RD New) are their south-west corners."""
        return shapely.box(x, y, x + 100, y + 100)


    def bro_locations(kind, version, area):
        """The registered BRO objects of one kind ("cpt", "bhrgt") whose delivered location the area covers.

        BRO's search takes a WGS84 box and refuses one with more objects than its limit; the box of the
        largest buffer stays well under it.
        """
        lon0, lat0, lon1, lat1 = gpd.GeoSeries([area], crs=28992).to_crs(4326).total_bounds
        search = {
            "registrationPeriod": {"beginDate": "2015-01-01", "endDate": date.today().isoformat()},
            "area": {"boundingBox": {"lowerCorner": {"lon": lon0, "lat": lat0}, "upperCorner": {"lon": lon1, "lat": lat1}}},
        }
        request = Request(
            f"https://publiek.broservices.nl/sr/{kind}/{version}/characteristics/searches",
            data=json.dumps(search).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:
            root = ET.fromstring(response.read())
        rows = []
        for obj in root.iterfind("{*}dispatchDocument/*"):
            pos = obj.findtext("{*}deliveredLocation/{*}pos")
            if pos is None or obj.findtext("{*}deregistered") != "nee":
                continue
            point = shapely.Point(map(float, pos.split()))
            if area.covers(point):
                rows.append({"bro_id": obj.findtext("{*}broId"), "kind": kind, "geometry": point})
        return rows


    def read_bro_cpt(path):
        """A BRO CPT XML's readings: z in m NAP, qc, fs and u2 in MPa, Rf in %."""
        # The columns of the values block, in this order (dscpt/1.1); -999999 is a missing value
        parameters = [
            "penetrationLength", "depth", "elapsedTime", "coneResistance", "correctedConeResistance",
            "netConeResistance", "magneticFieldStrengthX", "magneticFieldStrengthY", "magneticFieldStrengthZ",
            "magneticFieldStrengthTotal", "electricalConductivity", "inclinationEW", "inclinationNS",
            "inclinationX", "inclinationY", "inclinationResultant", "magneticInclination",
            "magneticDeclination", "localFriction", "poreRatio", "temperature", "porePressureU1",
            "porePressureU2", "porePressureU3", "frictionRatio",
        ]
        root = ET.parse(path).getroot()
        x, y = map(float, root.findtext(".//{*}deliveredLocation/{*}location/{*}pos").split())
        offset = float(root.findtext(".//{*}deliveredVerticalPosition/{*}offset"))
        values = root.findtext(".//{*}conePenetrationTest//{*}values")
        readings = pl.read_csv(
            io.StringIO(values.strip().replace(";", "\n")),
            has_header=False,
            new_columns=parameters,
            schema_overrides=dict.fromkeys(parameters, pl.Float64),
        ).with_columns(pl.all().replace(-999999.0, None))
        return readings.select(
            bro_id=pl.lit(root.findtext(".//{*}broId")),
            x=pl.lit(x),
            y=pl.lit(y),
            report_date=pl.lit(root.findtext(".//{*}researchReportDate/{*}date")),
            cpt_standard=pl.lit(root.findtext(".//{*}cptStandard")),
            z=offset - pl.coalesce("depth", "penetrationLength"),
            qc=pl.col("coneResistance"),
            fs=pl.col("localFriction"),
            # Rf as delivered, else from fs and qc
            rf=pl.coalesce("frictionRatio", 100 * pl.col("localFriction") / pl.col("coneResistance")),
            u2=pl.col("porePressureU2"),
        )

    return bro_locations, geotop_cells, read_bro_cpt


@app.cell(hide_code=True)
def selection(
    bro_locations,
    buffer_distance,
    footprint_rd,
    geotop_cells,
    gpd,
    mo,
    np,
    shapely,
):
    buffer_rd = footprint_rd.buffer(buffer_distance.value)
    _xmin, _ymin, _xmax, _ymax = buffer_rd.bounds
    _x, _y = np.meshgrid(np.arange(_xmin // 100 * 100, _xmax, 100), np.arange(_ymin // 100 * 100, _ymax, 100))
    _cells = geotop_cells(_x, _y)
    _touched = shapely.intersects(_cells, buffer_rd)
    geotop_columns = gpd.GeoDataFrame(
        {"geotop_x": _x[_touched].astype(int), "geotop_y": _y[_touched].astype(int)}, geometry=_cells[_touched], crs=28992
    )
    selection_rd = geotop_columns.union_all()

    with mo.status.spinner("Searching the BRO for CPTs and geotechnical boreholes…"):
        selected_locations = gpd.GeoDataFrame(
            [*bro_locations("cpt", "v1", selection_rd), *bro_locations("bhrgt", "v2", selection_rd)],
            columns=["bro_id", "kind", "geometry"],
            geometry="geometry",
            crs=28992,
        )
    selected_cpt_ids = sorted(selected_locations.bro_id[selected_locations.kind == "cpt"])
    selected_bhrgt_ids = sorted(selected_locations.bro_id[selected_locations.kind == "bhrgt"])
    mo.md(
        f"**{len(geotop_columns)} GeoTOP columns · {len(selected_cpt_ids)} CPTs · {len(selected_bhrgt_ids)} geotechnical boreholes** in or on the touched columns."
    )
    return (
        buffer_rd,
        geotop_columns,
        selected_bhrgt_ids,
        selected_cpt_ids,
        selected_locations,
        selection_rd,
    )


@app.cell(hide_code=True)
def selection_map(
    buffer_rd,
    folium,
    footprint_rd,
    geotop_columns,
    gpd,
    selected_locations,
):
    selection_map = folium.Map(tiles=None)
    # A fixed height: marimo shows the map in an iframe of its figure's height
    folium.Figure(height=550).add_child(selection_map)
    folium.TileLayer(
        tiles="https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg",
        attr="Kadaster / PDOK",
        name="Aerial photo",
        max_zoom=19,
    ).add_to(selection_map)
    folium.TileLayer("OpenStreetMap").add_to(selection_map)
    for _name, _shapes, _color, _fill in [
        (
            "Building footprint",
            gpd.GeoSeries([footprint_rd], crs=28992),
            "#dc2626",
            0.25,
        ),
        ("Buffer", gpd.GeoSeries([buffer_rd], crs=28992), "#f59e0b", 0.1),
        ("Touched GeoTOP columns", geotop_columns, "#ffffff", 0.05),
    ]:
        folium.GeoJson(
            _shapes.to_crs(4326).to_json(),
            name=_name,
            style_function=lambda _, color=_color, fill=_fill: {
                "color": color,
                "weight": 2,
                "fillOpacity": fill,
            },
        ).add_to(selection_map)
    for _kind, _name, _color in [
        ("cpt", "CPTs", "#7c3aed"),
        ("bhrgt", "Geotechnical boreholes", "#ea580c"),
    ]:
        _points = selected_locations[selected_locations.kind == _kind]
        if _points.empty:
            continue
        folium.GeoJson(
            _points.to_crs(4326).to_json(),
            name=_name,
            marker=folium.CircleMarker(
                radius=4, color=_color, fill=True, fill_opacity=0.9
            ),
            tooltip=folium.GeoJsonTooltip(["bro_id"], labels=False),
        ).add_to(selection_map)
    folium.LayerControl().add_to(selection_map)
    _west, _south, _east, _north = geotop_columns.to_crs(4326).total_bounds
    selection_map.fit_bounds([[_south, _west], [_north, _east]])
    selection_map
    return


@app.cell(hide_code=True)
def download_controls(mo):
    download_selected = mo.ui.run_button(label="Download selected data")
    mo.vstack([download_selected, mo.md("Fetches GeoTOP voxel values and BRO source XMLs into the local, Git-ignored `data/` folder. Moving the slider only updates the preview.")])
    return (download_selected,)


@app.cell(hide_code=True)
def download(
    BIM_URL,
    DATA_DIR,
    MODEL_BOTTOM_NAP,
    bromodels,
    buffer_distance,
    buffer_rd,
    download_selected,
    geotop_cells,
    json,
    mo,
    np,
    pl,
    read_bro_cpt,
    selected_bhrgt_ids,
    selected_cpt_ids,
    selection_rd,
    shapely,
    urlopen,
    xr,
):
    mo.stop(
        not download_selected.value,
        mo.md("Select an area above, then press **Download selected data**."),
    )


    def _bro_xml(kind, version, bro_id):
        """A BRO object's XML, downloaded into data/<kind>_xml/ the first time."""
        path = DATA_DIR / f"{kind}_xml" / f"{bro_id}.xml"
        if not path.exists():
            path.parent.mkdir(exist_ok=True)
            with urlopen(f"https://publiek.broservices.nl/sr/{kind}/{version}/objects/{bro_id}", timeout=60) as response:
                path.write_bytes(response.read())
        return path


    with mo.status.spinner("Downloading GeoTOP…"):
        _west, _south, _east, _north = selection_rd.bounds
        _geotop = bromodels.GTM.GeoTop.GeoTopDomain(west=_west, south=_south, east=_east, north=_north, bottom=MODEL_BOTTOM_NAP)
        # All GeoTOP variables, in the touched columns only
        _x, _y = np.meshgrid(_geotop.x, _geotop.y)
        _touched = xr.DataArray(
            shapely.intersects(geotop_cells(_x, _y), buffer_rd), coords={"y": _geotop.y, "x": _geotop.x}, dims=("y", "x")
        )
        _geotop = _geotop.where(_touched).dropna("x", how="all").dropna("y", how="all").load()

    _cpts = pl.concat(
        read_bro_cpt(_bro_xml("cpt", "v1", _bro_id))
        for _bro_id in mo.status.progress_bar(selected_cpt_ids, title="Downloading CPTs")
    ).filter(pl.col("qc") > 0)

    for _bro_id in mo.status.progress_bar(selected_bhrgt_ids, title="Downloading geotechnical boreholes"):
        _bro_xml("bhrgt", "v2", _bro_id)

    # Replace the notebook inputs only once everything has downloaded
    _geotop.to_netcdf(DATA_DIR / "geotop.nc")
    _cpts.write_parquet(DATA_DIR / "cpts.parquet")
    (DATA_DIR / "selection.json").write_text(
        json.dumps(
            {
                "buffer_m": buffer_distance.value,
                "bottom_nap": MODEL_BOTTOM_NAP,
                "bim_url": BIM_URL,
                "cpt_ids": selected_cpt_ids,
                "bhrgt_ids": selected_bhrgt_ids,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    mo.md(
        f"Saved {_geotop.sizes['x'] * _geotop.sizes['y']} GeoTOP columns' grid with {len(_geotop.data_vars)} variables, {_cpts['bro_id'].n_unique()} CPTs and {len(selected_bhrgt_ids)} geotechnical boreholes under `{DATA_DIR}`."
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## GeoTOP as a BimDataFrame

    The downloaded voxels in a bimpolars BimDataFrame, one row per voxel: a box mesh in GeoTOP's
    lithology colour, the stratigraphic unit as `class`, and the voxel's GeoTOP values in the property
    set `GeoTOP`. It is written to `data/geotop_bimdf.parquet` for the next notebooks, and rebuilt
    whenever a download replaces `data/geotop.nc`.
    """)
    return


@app.cell(hide_code=True)
def geotop_legends(bromodels, mo, pl):
    def _with_hex(legend):
        """A GeoTOP legend with its colour as a hex string, first."""
        return legend.with_columns(
            color_hex=pl.struct("RED_DEC", "GREEN_DEC", "BLUE_DEC").map_elements(
                lambda c: f"#{c['RED_DEC']:02x}{c['GREEN_DEC']:02x}{c['BLUE_DEC']:02x}", return_dtype=pl.String
            )
        ).select("color_hex", pl.all().exclude("color_hex"))


    lithok_map = _with_hex(
        pl.from_pandas(bromodels.GeoTop.geotop_lithology_class())
        .filter(pl.col("VOXEL_NR").is_not_null())
        .with_columns(pl.col("VOXEL_NR").cast(pl.Int64))
    )
    strat_map = _with_hex(pl.from_pandas(bromodels.GeoTop.geotop_stratigraphic_unit()))
    mo.ui.tabs(
        {
            _name: mo.ui.table(
                _legend,
                style_cell=lambda _row, column, value: {"backgroundColor": value} if column == "color_hex" else {},
            )
            for _name, _legend in [("GeoTOP lithology classes", lithok_map), ("GeoTOP stratigraphic units", strat_map)]
        }
    )
    return lithok_map, strat_map


@app.cell
def geotop_file(DATA_DIR, mo):
    # The voxels' file: the cells that read it run again when a download replaces it
    geotop_nc = mo.watch.file(DATA_DIR / "geotop.nc")
    return (geotop_nc,)


@app.cell
def geotop_read(Path, geotop_nc, mo, xr):
    mo.stop(not Path(geotop_nc).exists(), mo.md("Download the selected data first."))
    # Closing the file lets a download, or another notebook, replace it
    with xr.open_dataset(geotop_nc) as _geotop_nc:
        geotop_xr = _geotop_nc.load()
    geotop_xr
    return (geotop_xr,)


@app.cell
def geotop_voxels(geotop_xr, lithok_map, mo, pl, strat_map):
    # One row per voxel with a value. x, y and z are the xarray indices, which polars needs as columns.
    geotop_df = (
        pl.from_pandas(geotop_xr.to_dataframe().reset_index())
        .filter(pl.col("strat").is_not_null() & pl.col("lithok").is_not_null())
        .with_columns(
            pl.col("x", "y", "z").cast(pl.Float64),
            pl.col("strat", "lithok").cast(pl.Int64),
        )
        .join(
            strat_map.select(
                pl.col("VOXEL_NR").cast(pl.Int64).alias("strat"),
                pl.col("STR_UNIT_CD").alias("stratigraphic_unit"),
                pl.col("DESCRIPTION").alias("geologische_eenheid"),
                pl.col("color_hex").alias("strat_hex"),
            ),
            on="strat",
            how="left",
        )
        .join(
            lithok_map.select(
                pl.col("VOXEL_NR").alias("lithok"),
                pl.col("LITHO_CLASS_CD").alias("lithoklasse"),
                pl.col("DESCRIPTION").alias("grondsoort"),
                pl.col("color_hex").alias("lithok_hex"),
            ),
            on="lithok",
            how="left",
        )
    )
    mo.ui.table(
        geotop_df,
        style_cell=lambda _row, column, value: {"backgroundColor": value} if column.endswith("_hex") else {},
    )
    return (geotop_df,)


@app.cell
def geotop_units(geotop_df, mo, pl):
    # One row per geological unit, from the top down: its topmost voxel, with the number of voxels in the unit.
    # The unit and soil type come first, in their GeoTOP colours.
    _names = ["geologische_eenheid", "stratigraphic_unit", "grondsoort", "lithoklasse"]
    _units = (
        geotop_df.sort("z", descending=True)
        .group_by("geologische_eenheid", maintain_order=True)
        .agg(pl.all().first(), pl.len().alias("n_voxels"))
        .select(*_names, "n_voxels", pl.all().exclude(*_names, "n_voxels"))
    )
    _colors = dict(zip(_names, [_units["strat_hex"]] * 2 + [_units["lithok_hex"]] * 2))


    def _style(row, column, value):
        if column not in _colors:
            return {}
        _color = _colors[column][int(row)]
        # Dark text on light colours, white on dark ones
        _r, _g, _b = (int(_color[_i : _i + 2], 16) for _i in (1, 3, 5))
        return {"backgroundColor": _color, "color": "black" if 0.299 * _r + 0.587 * _g + 0.114 * _b > 140 else "white"}


    mo.ui.table(_units.drop("strat_hex", "lithok_hex"), style_cell=_style, page_size=_units.height, selection=None)
    return


@app.cell
def voxel_size():
    # GeoTOP's x and y are the south-west corners of its 100 m columns (see geotop_cells); z is the
    # centre of each 0.5 m voxel
    VOXEL_SIZE = (100.0, 100.0, 0.5)
    return (VOXEL_SIZE,)


@app.cell
def geotop_boxes(VOXEL_SIZE, bpl, geotop_df, pl):
    # The 12 triangles of a box whose corners 0-3 are at the bottom and 4-7 at the top, each
    # counterclockwise from the south-west, wound outwards
    _BOX_FACES = [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 1, 2, 6, 1, 6, 5, 2, 3, 7, 2, 7, 6, 3, 0, 4, 3, 4, 7]
    _dx, _dy, _dz = VOXEL_SIZE
    _x0, _x1 = pl.col("x"), pl.col("x") + _dx
    _y0, _y1 = pl.col("y"), pl.col("y") + _dy
    _z0, _z1 = pl.col("z") - _dz / 2, pl.col("z") + _dz / 2
    _rgb = [pl.col("lithok_hex").str.slice(_i, 2).str.to_integer(base=16) / 255 for _i in (1, 3, 5)]

    geotop_rd = bpl.BimDataFrame(
        geotop_df.select(
            id=pl.format("geotop {} {} {}", pl.col("x").cast(pl.Int64), pl.col("y").cast(pl.Int64), "z"),
            name=pl.format("{}, {}", "stratigraphic_unit", "grondsoort"),
            **{"class": pl.col("stratigraphic_unit").cast(pl.Categorical)},
            properties=pl.struct(pl.struct(pl.all().exclude("strat_hex", "lithok_hex")).alias("GeoTOP")),
            mesh=pl.struct(
                vertices=pl.concat_list(
                    _x0, _y0, _z0, _x1, _y0, _z0, _x1, _y1, _z0, _x0, _y1, _z0,
                    _x0, _y0, _z1, _x1, _y0, _z1, _x1, _y1, _z1, _x0, _y1, _z1,
                ),
                faces=pl.lit(_BOX_FACES, dtype=pl.List(pl.UInt32)),
                styles=pl.concat_list(
                    pl.struct(
                        name=pl.col("grondsoort"),
                        rgba=pl.concat_list(*_rgb, pl.lit(1.0)).list.to_array(4),
                        face_count=pl.lit(len(_BOX_FACES) // 3, dtype=pl.UInt32),
                    )
                ),
            ).cast(bpl.MESH_DTYPE),
            bbox=pl.struct(xmin=_x0, ymin=_y0, zmin=_z0, xmax=_x1, ymax=_y1, zmax=_z1),
        ),
        crs="EPSG:7415",
    )
    geotop_rd
    return (geotop_rd,)


@app.cell
def geotop_bimdf(DATA_DIR, bpl, geotop_rd):
    # The site origin: the plan centre of the GeoTOP columns at NAP 0 m, with the axes along RD's.
    # GeoSpeckleViewer draws a model near its CRS's origin.
    _bbox = geotop_rd["bbox"].struct.unnest()
    site_origin = (
        (_bbox["xmin"].min() + _bbox["xmax"].max()) / 2,
        (_bbox["ymin"].min() + _bbox["ymax"].max()) / 2,
        0.0,
    )
    site_crs = bpl.georeferenced_bim_crs("EPSG:7415", *site_origin, 0.0, unit=geotop_rd, name="GeoTOP")
    geotop_bimdf = bpl.to_crs(geotop_rd, site_crs)
    geotop_bimdf.write_parquet(DATA_DIR / "geotop_bimdf.parquet")
    geotop_bimdf
    return (geotop_bimdf,)


@app.cell(hide_code=True)
def viewer_intro(mo):
    mo.md(r"""
    ### GeoTOP in the GeoSpeckleViewer

    The voxels among the buildings of PDOK's 3D BAG. Click a voxel to see its row below.
    """)
    return


@app.cell(hide_code=True)
def viewer_color(mo):
    color_by = mo.ui.radio(
        options={"Lithology": None, "Stratigraphic unit": "class"},
        value="Lithology",
        label="Color the voxels by",
        inline=True,
    )
    color_by
    return (color_by,)


@app.cell(hide_code=True)
def viewer(GeoSpeckleViewer, color_by, geotop_bimdf, mo, pdok_3d_buildings):
    geotop_viewer = mo.ui.anywidget(
        GeoSpeckleViewer(
            geotop_bimdf,
            color=color_by.value,
            # ground_map=osm_ground_map(geotop_bimdf),
            tilesets=[pdok_3d_buildings(geotop_bimdf)],
            height=550,
        )
    )
    geotop_viewer
    return (geotop_viewer,)


@app.cell
def viewer_selection(geotop_bimdf, geotop_viewer, pl):
    # The voxels selected in the GeoSpeckleViewer
    selected_voxels = geotop_bimdf.filter(
        pl.col("id").is_in([_obj["applicationId"] for _obj in geotop_viewer.value["selected"]])
    )
    selected_voxels.select("id", "name", "class", pl.col("properties").struct.field("GeoTOP").struct.unnest())
    return


if __name__ == "__main__":
    app.run()
