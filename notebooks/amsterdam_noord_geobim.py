# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "altair==6.3.0",
#     "anywidget==0.11.0",
#     "bimpolars[speckle]",
#     "folium==0.20.0",
#     "geopandas==1.2.0",
#     "mapclassify==2.11.0",
#     "marimo",
#     "marimo-lens==0.2.4",
#     "matplotlib==3.11.2",
#     "numpy==2.5.4",
#     "obstore>=0.11.1",
#     "polars==2.1.0",
#     "pyproj==3.8.0",
#     "specklewidgets",
#     "traitlets==5.16.1",
#     "zarr>=3",
# ]
#
# [tool.uv.sources]
# bimpolars = { git = "https://github.com/bedrock-engineer/bimpolars" }
# specklewidgets = { git = "https://github.com/bedrock-engineer/specklestuff" }
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    from pathlib import Path
    from urllib.request import urlopen

    import altair as alt
    import anywidget
    import bimpolars as bpl
    import geopandas as gpd
    import marimo as mo
    import numpy as np
    import polars as pl
    import pyproj
    import traitlets
    import zarr
    from marimo_lens import Lens
    from obstore.store import HTTPStore
    from specklewidgets import GeoSpeckleViewer, models_gz
    from specklewidgets.bim import bim_objects
    from specklewidgets.geo import osm_ground_map, pdok_3d_buildings

    from cpt_robertson_classification import SOIL_BEHAVIOR_COLORS, robertson

    # RD New + NAP to WGS 84 follows RDNAPTRANS2018 only with the NSGI grids, which PROJ fetches
    pyproj.network.set_network_enabled(True)
    return (
        GeoSpeckleViewer,
        HTTPStore,
        Lens,
        Path,
        SOIL_BEHAVIOR_COLORS,
        alt,
        anywidget,
        bim_objects,
        bpl,
        gpd,
        json,
        mo,
        models_gz,
        np,
        osm_ground_map,
        pdok_3d_buildings,
        pl,
        robertson,
        traitlets,
        urlopen,
        zarr,
    )


@app.cell
def _(Lens):
    # marimo-lens: select a region of any output and add a note for the notebook agent
    lens = Lens()
    lens
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Amsterdam Noord GeoBIM

    Revit's advanced sample project placed on a plot at Overhoeks, Amsterdam Noord: the
    architecture and structure models combined into one BimDataFrame, as
    `speckle/rvt_advanced_sample_project_to_r2.py` pushed it to R2, among OpenStreetMap and the
    3D BAG. With it, the interpreted CPTs and SBTn volumes of the 10 m / 25 cm run, as
    `sync_r2.py` pushed them to R2 from `06_bimdataframes.py`, without the SBTn zones 1, 8 and 9,
    which hardly occur.
    """)
    return


@app.cell(hide_code=True)
def _(bpl):
    # Architecture and structural models of the "Revit advanced sample project" combined, and georeferenced in Amsterdam Noord on Cloudflare R2:
    combined_arch_str_bimdf = bpl.read_parquet(
        "https://r2.eu.bedrock.engineer/bimpolars/rvt-advanced-sample/rvt-advanced-sample-combined-arch-str-bdf.parquet"
    )
    # combined_arch_str_bimdf
    return (combined_arch_str_bimdf,)


@app.cell(hide_code=True)
def _():
    # The SBTn zones left out of the CPTs and volumes, which hardly occur: zone 1 in 49 cells and 5 CPTs, zones 8 and 9 in 8
    # cells and no CPT
    SBTN_LEFT_OUT = ["1 Sensitive fine-grained", "8 Very stiff sand to clayey sand", "9 Very stiff fine-grained"]
    return (SBTN_LEFT_OUT,)


@app.cell(hide_code=True)
def _(SBTN_LEFT_OUT, bpl, combined_arch_str_bimdf, pl):
    # The interpreted CPTs on Cloudflare R2, at the run's 25 cm: a cylinder per layer of the same SBTn, in the building's CRS
    cpts_interpreted_bimdf = bpl.to_crs(
        bpl.read_parquet(
            "https://r2.eu.bedrock.engineer/nl-amsterdam-noord/cpts_interpreted_25cm.parquet"
        ).filter(~pl.col("class").cast(pl.String).is_in(SBTN_LEFT_OUT)),
        combined_arch_str_bimdf.crs,
    )
    # cpts_interpreted_bimdf
    return (cpts_interpreted_bimdf,)


@app.cell(hide_code=True)
def _(SBTN_LEFT_OUT, bpl, combined_arch_str_bimdf, pl):
    # The SBTn volumes of the 10 m / 25 cm run on Cloudflare R2: one per most likely SBTn, the outer surface of its cells, in the building's CRS
    sbtn_volumes_bimdf = bpl.to_crs(
        bpl.read_parquet(
            "https://r2.eu.bedrock.engineer/nl-amsterdam-noord/sbtn_volumes_25cm.parquet"
        ).filter(~pl.col("class").cast(pl.String).is_in(SBTN_LEFT_OUT)),
        combined_arch_str_bimdf.crs,
    )
    # sbtn_volumes_bimdf
    return (sbtn_volumes_bimdf,)


@app.cell(hide_code=True)
def _(combined_arch_str_bimdf, gpd):
    # The elements' footprints in plan, in longitude and latitude without heights
    combined_arch_str_geodf = gpd.GeoDataFrame(
        combined_arch_str_bimdf.select(
            "model_name", "class", "name", "id"
        ).to_pandas(),
        geometry=gpd.GeoSeries.from_wkb(
            combined_arch_str_bimdf["geog"].to_numpy(), crs="OGC:CRS84"
        ).force_2d(),
    )
    # The whole model's footprint: the largest part of the union of the element footprints, without the
    # slivers of arch's line-like Generic Models
    combined_arch_str_outline = gpd.GeoDataFrame(
        {"layer": ["Footprint of arch and str combined"]},
        geometry=[
            max(
                gpd.GeoSeries([combined_arch_str_geodf.union_all()]).explode(),
                key=lambda _part: _part.area,
            )
        ],
        crs="OGC:CRS84",
    )
    return combined_arch_str_geodf, combined_arch_str_outline


@app.cell
def _(
    bim_objects,
    combined_arch_str_bimdf,
    cpts_interpreted_bimdf,
    mo,
    pl,
    sbtn_volumes_bimdf,
):
    # What the viewer shows. An SBTn in the legend shows or hides its volume; the CPTs' cylinders have the same colors.
    _colors = sbtn_volumes_bimdf["mesh"].struct.field("styles").list.first().struct.field("rgba").to_list()
    show_architecture = mo.ui.checkbox(value=False, label="Architecture")
    show_structure = mo.ui.checkbox(value=True, label="Structure")
    show_cpts = mo.ui.checkbox(value=True, label="Interpreted CPTs")
    show_volumes = mo.ui.checkbox(value=True, label="SBTn volumes")
    show_buildings = mo.ui.checkbox(value=True, label="3D buildings")
    show_map = mo.ui.checkbox(value=False, label="Map")
    shown_sbtn = mo.ui.dictionary(
        {
            _label: mo.ui.checkbox(
                value=True,
                label=f'<span style="display: inline-flex; gap: 6px;"><span style="flex: none; width: 12px; height: 12px; margin-top: 4px; background: rgb({_rgba[0] * 255:.0f} {_rgba[1] * 255:.0f} {_rgba[2] * 255:.0f}); border: 1px solid #bbb;"></span>{_label}</span>',
            )
            for _label, _rgba in zip(sbtn_volumes_bimdf["name"], _colors)
        }
    )
    # Laid out here: a cell that references the checkboxes themselves runs again with each click, and the viewer's cell
    # would then build a new viewer and fetch the 3D BAG again
    viewer_controls = mo.vstack(
        [
            mo.md("**3D Geospatial Context**"),
            show_map,
            show_buildings,
            mo.md("**BIM**"),
            show_architecture,
            show_structure,
            show_cpts,
            show_volumes,
            mo.md("**SBTn**"),
            *shown_sbtn.elements.values(),
        ],
        gap=0.25,
    )
    # Each volume, the CPTs and both building models once as a viewer model, so that showing or hiding one only packs the models again
    volume_models = {_label: bim_objects(sbtn_volumes_bimdf.filter(pl.col("name") == _label)) for _label in sbtn_volumes_bimdf["name"]}
    cpt_model = bim_objects(cpts_interpreted_bimdf)
    architecture_model = bim_objects(combined_arch_str_bimdf.filter(pl.col("model_name") == "rvt-advanced-sample-arch"))
    structure_model = bim_objects(combined_arch_str_bimdf.filter(pl.col("model_name") == "rvt-advanced-sample-str"))
    return (
        architecture_model,
        cpt_model,
        show_architecture,
        show_buildings,
        show_cpts,
        show_map,
        show_structure,
        show_volumes,
        shown_sbtn,
        structure_model,
        viewer_controls,
        volume_models,
    )


@app.cell(hide_code=True)
def _(
    GeoSpeckleViewer,
    mo,
    osm_ground_map,
    pdok_3d_buildings,
    sbtn_volumes_bimdf,
    viewer_controls,
):
    # OpenStreetMap and the 3D BAG's buildings around the volumes, which reach further than the building. One viewer
    # that keeps them when the checkboxes change what it shows.
    ground_map = osm_ground_map(sbtn_volumes_bimdf)
    buildings_tileset = pdok_3d_buildings(sbtn_volumes_bimdf)
    viewer_widget = GeoSpeckleViewer(height=550)
    geobim_viewer = mo.ui.anywidget(viewer_widget)
    mo.hstack([geobim_viewer, viewer_controls], widths=[5, 2], align="start")
    return buildings_tileset, geobim_viewer, ground_map, viewer_widget


@app.cell(hide_code=True)
def _(color_by, mo, probability_of):
    # The zone can only be chosen when the cells show its probability
    mo.vstack([color_by, probability_of] if color_by.value == "probability" else [color_by])
    return


@app.cell(hide_code=True, expand_output=True)
def _(
    CrossSections,
    Path,
    SBTN_ZONES,
    SOIL_BEHAVIOR_COLORS,
    cell_size,
    combined_arch_str_outline,
    cpt_samples,
    domain_names,
    json,
    mo,
    pl,
    soil_cells,
    unit_names,
):
    # Made once; section_values colors it. The sections start through the building, at the CPT readings' median level.
    _cpts = (
        cpt_samples.filter(pl.col("qc") > 0)
        .sort("z", descending=True)
        .group_by("bro_id", maintain_order=True)
        .agg(pl.first("x", "y"), "z", "qc")
    )
    _zones = sorted(SBTN_ZONES)
    _corners = soil_cells.select(
        (pl.col("x") - cell_size["x"] / 2).round(3),
        (pl.col("y") - cell_size["y"] / 2).round(3),
        "z",
        "unit",
        pl.col("zone").replace_strict({_zone: _i for _i, _zone in enumerate(_zones)}, return_dtype=pl.Int64),
    )
    _building = combined_arch_str_outline.to_crs("EPSG:28992").geometry.iloc[0]


    def _cell_at(coordinate, axis):
        """The south-west corner of the cell that a coordinate lies in"""
        _start = _corners[axis].min()
        return round(_start + (coordinate - _start) // cell_size[axis] * cell_size[axis], 3)


    _domain_colors = json.loads((Path(mo.notebook_dir()) / "simulation_domains.json").read_text(encoding="utf-8"))["colors"]
    _median_z = _cpts["z"].explode().median()
    # The CPT nearest the building is selected first
    _nearest = _cpts.sort((pl.col("x") - _building.centroid.x) ** 2 + (pl.col("y") - _building.centroid.y) ** 2)["bro_id"][0]
    section_view = CrossSections(
        voxels=_corners.rows(),
        cell=cell_size,
        units=[{"code": _name, "name": _name, "color": "#cccccc"} for _name in unit_names],
        lithologies=[{"name": SBTN_ZONES[_zone], "color": SOIL_BEHAVIOR_COLORS[_zone]} for _zone in _zones],
        cpts=_cpts.to_dicts(),
        domains=[{"name": _name, "color": _domain_colors[_name]} for _name in domain_names],
        domain_of=soil_cells["domain"].to_list(),
        footprints=[list(_building.exterior.coords)],
        x=_cell_at(_building.centroid.x, "x"),
        y=_cell_at(_building.centroid.y, "y"),
        z=min(soil_cells["z"].unique().to_list(), key=lambda _z: abs(_z - _median_z)),
        selected_cpt=_nearest,
    )
    cross_sections = mo.ui.anywidget(section_view)
    cross_sections
    return cross_sections, section_view


@app.cell(hide_code=True, expand_output=True)
def _(
    SBTN_ZONES,
    SOIL_BEHAVIOR_COLORS,
    alt,
    cell_size,
    classified_samples,
    get_selected_cpt,
    mo,
    np,
    pl,
    sbtn_zone_numbers,
    soil_cells,
    soil_values,
    zone_probabilities,
):
    _bro_id = get_selected_cpt()
    mo.stop(not _bro_id, mo.md("Click a CPT in the plan above."))
    _cpt = classified_samples.filter(
        (pl.col("bro_id") == _bro_id) & pl.col("zone").is_in(list(SBTN_ZONES))
    ).with_columns(
        label=pl.col("zone").replace_strict(
            SBTN_ZONES, return_dtype=pl.String
        ),
        top=pl.col("z") + cell_size["z"] / 2,
        bottom=pl.col("z") - cell_size["z"] / 2,
    )
    mo.stop(
        _cpt.is_empty(),
        mo.md(f"{_bro_id} has no samples with both qc and fs."),
    )
    _x, _y = _cpt["x"][0], _cpt["y"][0]
    # The column of cells the CPT lies in
    _column = (
        soil_cells.with_row_index("cell")
        .filter(
            ((pl.col("x") - _x).abs() <= cell_size["x"] / 2)
            & ((pl.col("y") - _y).abs() <= cell_size["y"] / 2)
        )
        .sort("z")
    )
    _index = _column["cell"].to_numpy()
    _z = _column["z"].to_numpy()
    _y_scale = alt.Scale(
        domain=[
            float(min(_z.min(), _cpt["z"].min())) - 0.5,
            float(max(_z.max(), _cpt["z"].max())) + 0.5,
        ]
    )
    _y_axis = alt.Y("z:Q", title="z (m NAP)", scale=_y_scale)
    _band = _column.select("z").with_columns(
        *(
            pl.Series(_p, soil_values[f"ic_{_p}"][_index])
            for _p in ("p10", "p50", "p90")
        )
    )
    _zone_scale = alt.Scale(
        domain=list(SBTN_ZONES.values()),
        range=[SOIL_BEHAVIOR_COLORS[_zone] for _zone in SBTN_ZONES],
    )
    # Ic, with the boundaries of zones 2 to 7
    _ic_axis = alt.X("value:Q", title="Ic", scale=alt.Scale(domain=[1, 4.5]))
    _rules = (
        alt.Chart(pl.DataFrame({"value": [1.31, 2.05, 2.60, 2.95, 3.60]}))
        .mark_rule(color="#bbbbbb", strokeDash=[3, 3])
        .encode(x=_ic_axis)
    )
    _area = (
        alt.Chart(_band)
        .mark_area(opacity=0.25, color="#4c78a8", orient="horizontal")
        .encode(
            x=alt.X("p10:Q", title="Ic", scale=alt.Scale(domain=[1, 4.5])),
            x2="p90:Q",
            y=_y_axis,
        )
    )
    _median = (
        alt.Chart(_band)
        .mark_line(color="#1f3b63", strokeWidth=2)
        .encode(x="p50:Q", y=_y_axis, order="z:Q")
    )
    _points = (
        alt.Chart(_cpt.select("z", "label", value=pl.col("ic")))
        .mark_circle(color="black", size=18)
        .encode(
            x=_ic_axis,
            y=_y_axis,
            tooltip=["z", "label", alt.Tooltip("value:Q", format=".2f")],
        )
    )
    # The probability of each zone shown per cell, stacked from the lowest zone up; what is left to 1 is the zones left out
    _shown = [
        _k
        for _k, _zone in enumerate(sbtn_zone_numbers)
        if int(_zone) in SBTN_ZONES
    ]
    _stacked = np.cumsum(zone_probabilities[_shown][:, _index], axis=0)
    _bars = pl.concat(
        [
            pl.DataFrame(
                {
                    "z": _z,
                    "top": _z + cell_size["z"] / 2,
                    "bottom": _z - cell_size["z"] / 2,
                    "start": _stacked[_row] - zone_probabilities[_k, _index],
                    "end": _stacked[_row],
                    "probability": zone_probabilities[_k, _index],
                    "label": SBTN_ZONES[int(sbtn_zone_numbers[_k])],
                }
            )
            for _row, _k in enumerate(_shown)
        ]
    ).filter(pl.col("probability") > 0)
    _probabilities = (
        alt.Chart(_bars)
        .mark_rect()
        .encode(
            x=alt.X(
                "start:Q",
                title="Probability of each SBTn zone",
                scale=alt.Scale(domain=[0, 1]),
            ),
            x2="end:Q",
            y=alt.Y("top:Q", title=None, scale=_y_scale),
            y2="bottom:Q",
            color=alt.Color(
                "label:N",
                title="SBTn zone",
                scale=_zone_scale,
                legend=alt.Legend(labelLimit=220),
            ),
            tooltip=["z", "label", alt.Tooltip("probability:Q", format=".0%")],
        )
    )
    # The CPT's own zones
    _measured = (
        alt.Chart(_cpt)
        .mark_rect()
        .encode(
            y=alt.Y("top:Q", title=None, scale=_y_scale),
            y2="bottom:Q",
            color=alt.Color("label:N", scale=_zone_scale),
            tooltip=["z", "label"],
        )
        .properties(title="CPT", width=36, height=440)
    )
    mo.vstack(
        [
            alt.hconcat(
                (_rules + _area + _median + _points).properties(
                    width=280, height=440
                ),
                _probabilities.properties(width=240, height=440),
                _measured,
            ).resolve_scale(y="shared"),
            mo.md(
                f"{_bro_id} at x = {_x:.0f}, y = {_y:.0f}, in the column of cells of "
                f"{cell_size['x']:g} × {cell_size['y']:g} m around it: Ic of the realizations from P10 to P90 with their "
                "median and the CPT samples as dots, the probabilities of the zones, and the zones of the CPT samples."
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(cell_size, column_levels, json, np, pl, robertson, urlopen):
    # The CPT samples of the run's height as 03 makes them: the medians of the readings per sample in the voxels they
    # pass through. Their Ic and zone as 05 classifies them, with the settings of the classification on R2.
    _levels = np.sort(column_levels["z"].unique().to_numpy())[::-1]
    # The ground per GeoTOP column: the top of its highest voxel on the grid. The grid stops at the highest simulated level,
    # so in one column of 06's it lies 0.5 m lower, which moves a few samples next to a zone's boundary to the next zone.
    _ground_levels = column_levels.group_by("column_x", "column_y").agg((pl.col("z").max() + cell_size["z"] / 2).alias("ground_level"))
    _settings = json.loads(urlopen("https://r2.eu.bedrock.engineer/nl-amsterdam-noord/soil_model_25cm.json").read())["classification"]
    cpt_samples = (
        pl.read_parquet("https://r2.eu.bedrock.engineer/nl-amsterdam-noord/cpts.parquet")
        .with_columns(column_x=pl.col("x") // 100 * 100, column_y=pl.col("y") // 100 * 100, voxel_z=(pl.col("z") * 2).round() / 2)
        .with_columns(level=((pl.col("z") - pl.col("voxel_z") + 0.25) / cell_size["z"]).floor().clip(0, round(0.5 / cell_size["z"]) - 1))
        .with_columns(z=(pl.col("voxel_z") - 0.25 + (pl.col("level") + 0.5) * cell_size["z"]).round(3))
        .group_by("bro_id", "column_x", "column_y", "z")
        .agg(pl.first("x", "y"), pl.median("qc", "fs"))
        .join(column_levels.filter("simulated").drop("simulated"), on=["column_x", "column_y", "z"])
        .join(_ground_levels, on=["column_x", "column_y"])
        .sort("bro_id", "z")
    )
    _usable = cpt_samples.filter((pl.col("qc") > 0) & (pl.col("fs") > 0))
    _ids = _usable["bro_id"].unique().sort().to_list()
    _rows = _usable["bro_id"].replace_strict({_b: _i for _i, _b in enumerate(_ids)}, return_dtype=pl.Int64).to_numpy()
    _depths = np.searchsorted(-_levels, -_usable["z"].to_numpy())
    _qc, _fs = np.full((2, len(_ids), len(_levels)), np.nan)
    _qc[_rows, _depths] = _usable["qc"].to_numpy()
    _fs[_rows, _depths] = _usable["fs"].to_numpy()
    _ground = _usable.group_by("bro_id").agg(pl.first("ground_level")).sort("bro_id")["ground_level"].to_numpy()
    _result = robertson(_qc, _fs, _levels, _ground, gamma_missing=_settings["gamma_missing"])
    classified_samples = _usable.select("bro_id", "x", "y", "z").with_columns(
        pl.Series("zone", _result["zone"][_rows, _depths], dtype=pl.Int64),
        pl.Series("ic", _result["ic"][_rows, _depths]),
    )
    return classified_samples, cpt_samples


@app.cell(hide_code=True)
def _(HTTPStore, SBTN_LEFT_OUT, json, np, pl, zarr):
    # The soil model of the 10 m / 25 cm run on Cloudflare R2, as sync_r2.py pushed it: on its grid, in RD New + NAP. A
    # public bucket can't be listed, so the arrays are opened by name.
    _soil_model = zarr.open_group(
        zarr.storage.ObjectStore(
            HTTPStore.from_url("https://r2.eu.bedrock.engineer/nl-amsterdam-noord/soil_model.zarr"), read_only=True
        ),
        path="25cm",
        mode="r",
        zarr_format=3,
    )
    _x, _y, _z = (_soil_model[_axis][:] for _axis in ("x", "y", "z"))
    cell_size = {"x": float(_x[1] - _x[0]), "y": float(_y[1] - _y[0]), "z": float(_z[1] - _z[0])}
    SBTN_ZONES = {
        int(_zone): f"{_zone} {_name}"
        for _zone, _name in json.loads(_soil_model.attrs["soil_behavior_types"]).items()
        if f"{_zone} {_name}" not in SBTN_LEFT_OUT
    }
    # The cells of the zones shown, which leaves out those outside the simulation domains
    _most_likely = _soil_model["sbtn_most_likely"][:]
    _iz, _iy, _ix = np.nonzero(np.isin(_most_likely, list(SBTN_ZONES)))
    unit_names = _soil_model["stratigraphic_unit"].attrs["flag_meanings"].split()
    domain_names = _soil_model["domain"].attrs["flag_meanings"].split()
    soil_cells = pl.DataFrame(
        {
            "x": _x[_ix],
            "y": _y[_iy],
            "z": np.round(_z[_iz], 3),
            "zone": _most_likely[_iz, _iy, _ix].astype(np.int64),
            "unit": _soil_model["stratigraphic_unit"][:][_iz, _iy, _ix].astype(np.int64),
            "domain": _soil_model["domain"][:][_iz, _iy, _ix].astype(np.int64),
        }
    )
    # The levels of the GeoTOP voxels per column, on the cells' levels, and whether they lie in a simulation domain
    _uz, _uy, _ux = np.nonzero(_soil_model["stratigraphic_unit"][:] >= 0)
    column_levels = (
        pl.DataFrame(
            {
                "column_x": _x[_ux] // 100 * 100,
                "column_y": _y[_uy] // 100 * 100,
                "z": np.round(_z[_uz], 3),
                "simulated": _soil_model["domain"][:][_uz, _uy, _ux] >= 0,
            }
        )
        .group_by("column_x", "column_y", "z")
        .agg(pl.col("simulated").any())
    )
    soil_values = {
        _name: _soil_model[_name][:][_iz, _iy, _ix] for _name in ("qc_p50", "ic_p10", "ic_p50", "ic_p90")
    }
    # Per zone, the share of the realizations in it
    zone_probabilities = _soil_model["sbtn_probability"][:][:, _iz, _iy, _ix]
    sbtn_zone_numbers = _soil_model["sbtn_zone"][:]
    return (
        SBTN_ZONES,
        cell_size,
        column_levels,
        domain_names,
        sbtn_zone_numbers,
        soil_cells,
        soil_values,
        unit_names,
        zone_probabilities,
    )


@app.cell(hide_code=True)
def _(SBTN_ZONES, mo):
    color_by = mo.ui.radio(
        {
            "Most likely SBTn": "most likely",
            "Its probability": "its probability",
            "SBTn probability": "probability",
            "qc median": "qc median",
            "Ic median": "ic median",
            "Ic spread": "ic spread",
            "Simulation domain": "domain",
        },
        value="Most likely SBTn",
        label="Color by",
        inline=True,
    )
    probability_of = mo.ui.dropdown(
        {_label: _zone for _zone, _label in SBTN_ZONES.items()},
        value=SBTN_ZONES[3],
        label="SBTn zone",
    )
    return color_by, probability_of


@app.cell(hide_code=True)
def _(Path, anywidget, mo, traitlets):
    class CrossSections(anywidget.AnyWidget):
        """The cells from above at the level z, with a west–east section through the row of cells at y and a
        south–north one through the column of cells at x (x and y a cell's south-west corner)"""

        _esm = Path(mo.notebook_dir()) / "cross_sections.js"
        # Per cell: x, y, z and its indices in units and lithologies, which hold each stratigraphic unit's
        # code, name and color and each zone's name and color; the cells' size along x, y and z
        voxels = traitlets.List().tag(sync=True)
        cell = traitlets.Dict().tag(sync=True)
        units = traitlets.List().tag(sync=True)
        lithologies = traitlets.List().tag(sync=True)
        # Per CPT: its x and y, and its qc (MPa) per sample level z
        cpts = traitlets.List().tag(sync=True)
        # The domains' names and colors, and each cell's index in them
        domains = traitlets.List().tag(sync=True)
        domain_of = traitlets.List().tag(sync=True)
        # Rings of x and y to outline in the plan, such as a building's footprint
        footprints = traitlets.List([]).tag(sync=True)
        # Per cell, a value as float32 bytes, on a color scale {label, log, min, max, scheme}
        values = traitlets.Bytes().tag(sync=True)
        value_scale = traitlets.Dict().tag(sync=True)
        # What the cells are colored by: "value", "domain" or "lithology", set by Color by, so the widget offers
        # no buttons of its own
        color_modes = traitlets.List([]).tag(sync=True)
        color_by = traitlets.Unicode("lithology").tag(sync=True)
        # The CPT clicked in the plan, by its BRO ID
        selected_cpt = traitlets.Unicode("").tag(sync=True)
        x = traitlets.Float().tag(sync=True)
        y = traitlets.Float().tag(sync=True)
        z = traitlets.Float().tag(sync=True)

    return (CrossSections,)


@app.cell(hide_code=True)
def _(
    SBTN_ZONES,
    color_by,
    np,
    probability_of,
    sbtn_zone_numbers,
    section_view,
    soil_cells,
    soil_values,
    zone_probabilities,
):
    # The cross-sections colored by what color_by shows. Colored by a class, the value under the pointer is
    # the probability of the most likely zone.
    _its_probability = zone_probabilities[
        np.searchsorted(sbtn_zone_numbers, soil_cells["zone"].to_numpy()), np.arange(soil_cells.height)
    ]
    _values, _label, _log, _low, _high, _scheme = _its_probability, "Probability of the most likely SBTn zone", False, 0.0, 1.0, "viridis"
    if color_by.value == "probability":
        _index = int(np.searchsorted(sbtn_zone_numbers, probability_of.value))
        _values, _label = zone_probabilities[_index], f"Probability of {SBTN_ZONES[probability_of.value]}"
    elif color_by.value == "qc median":
        _values, _label, _log = soil_values["qc_p50"], "qc median (MPa)", True
        _low, _high = (float(_q) for _q in np.nanpercentile(_values, [2, 98]))
    elif color_by.value == "ic median":
        _values, _label, _low, _high = soil_values["ic_p50"], "Ic median", 1.31, 3.6
    elif color_by.value == "ic spread":
        _values = soil_values["ic_p90"] - soil_values["ic_p10"]
        _label, _low, _high, _scheme = "Ic P90 − P10", 0.0, float(np.nanpercentile(_values, 98)), "oranges"
    section_view.values = np.asarray(_values, dtype=np.float32).tobytes()
    section_view.value_scale = {"label": _label, "log": _log, "min": _low, "max": _high, "scheme": _scheme}
    section_view.color_by = {"most likely": "lithology", "domain": "domain"}.get(color_by.value, "value")
    return


@app.cell(hide_code=True)
def _(mo):
    # The CPT clicked in the cross-sections
    get_selected_cpt, set_selected_cpt = mo.state(None)
    return get_selected_cpt, set_selected_cpt


@app.cell(hide_code=True)
def _(cross_sections, get_selected_cpt, set_selected_cpt):
    # cross_sections also changes when the sections move; only another CPT goes on to what shows it
    if cross_sections.selected_cpt != get_selected_cpt():
        set_selected_cpt(cross_sections.selected_cpt)
    return


@app.cell(hide_code=True)
def _(buildings_tileset, ground_map, show_buildings, show_map, viewer_widget):
    # Apart from the models, so that showing or hiding these does not pack the models again
    viewer_widget.ground_map = dict(ground_map) if show_map.value else {}
    viewer_widget.tilesets = [dict(buildings_tileset)] if show_buildings.value else []
    return


@app.cell(hide_code=True)
def _(
    architecture_model,
    cpt_model,
    models_gz,
    show_architecture,
    show_cpts,
    show_structure,
    show_volumes,
    shown_sbtn,
    structure_model,
    viewer_widget,
    volume_models,
):
    # Through viewer_widget, not geobim_viewer, so that this cell does not run again each time the viewer reports back
    _models = [
        *(_model for _label, _model in volume_models.items() if show_volumes.value and shown_sbtn.value[_label]),
        *([cpt_model] if show_cpts.value else []),
        *([architecture_model] if show_architecture.value else []),
        *([structure_model] if show_structure.value else []),
    ]
    viewer_widget.objects_gz = models_gz(*_models) if _models else b""
    return


@app.cell(hide_code=True)
def _(combined_arch_str_geodf, combined_arch_str_outline, selected_elements):
    # The model's footprint on a web map, with the elements selected in the GeoSpeckleViewer in red.
    # The footprint is the background, without a tooltip; its legend also names the selection.
    _selected = combined_arch_str_geodf[
        combined_arch_str_geodf["id"].isin(selected_elements["id"])
    ]
    _categories = [
        *combined_arch_str_outline["layer"],
        *(["Selected in the GeoSpeckleViewer"] if len(_selected) else []),
    ]
    _map = combined_arch_str_outline.explore(
        column="layer",
        categories=_categories,
        cmap=["#4e79a7", "red"][: len(_categories)],
        tooltip=False,
    )
    if len(_selected):
        _selected.explore(m=_map, color="red")
    _map
    return


@app.cell(hide_code=True)
def _(combined_arch_str_bimdf, geobim_viewer, pl):
    # The elements selected in the GeoSpeckleViewer
    selected_elements = combined_arch_str_bimdf.filter(
        pl.col("id").is_in([_obj["applicationId"] for _obj in geobim_viewer.value["selected"]])
    )
    selected_elements
    return (selected_elements,)


@app.cell(hide_code=True)
def _(cpts_interpreted_bimdf, geobim_viewer, mo, pl, sbtn_volumes_bimdf):
    # The CPT layers and SBTn volumes selected in the GeoSpeckleViewer, with the statistics of what they merge
    _selected = [_obj["applicationId"] for _obj in geobim_viewer.value["selected"]]
    _rows = [
        _frame.filter(pl.col("id").is_in(_selected)).select(
            "id", "name", "class", pl.col("properties").struct.field(_set).struct.unnest()
        )
        for _frame, _set in ((sbtn_volumes_bimdf, "SBTn volume"), (cpts_interpreted_bimdf, "CPT"))
    ]
    mo.vstack([_row for _row in _rows if _row.height])
    return


if __name__ == "__main__":
    app.run()
