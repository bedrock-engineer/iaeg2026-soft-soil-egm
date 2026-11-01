# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "bimpolars[speckle]",
#     "folium==0.20.0",
#     "geopandas==1.2.0",
#     "mapclassify==2.11.0",
#     "marimo",
#     "marimo-lens==0.2.4",
#     "matplotlib==3.11.2",
#     "polars==2.1.0",
#     "pyproj==3.8.0",
#     "specklewidgets",
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
    import bimpolars as bpl
    import geopandas as gpd
    import marimo as mo
    import polars as pl
    import pyproj
    from marimo_lens import Lens
    from specklewidgets import GeoSpeckleViewer
    from specklewidgets.geo import osm_ground_map, pdok_3d_buildings

    # RD New + NAP to WGS 84 follows RDNAPTRANS2018 only with the NSGI grids, which PROJ fetches
    pyproj.network.set_network_enabled(True)
    return (
        GeoSpeckleViewer,
        Lens,
        bpl,
        gpd,
        mo,
        osm_ground_map,
        pdok_3d_buildings,
        pl,
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
    3D BAG.
    """)
    return


@app.cell(hide_code=True)
def _(bpl):
    # Architecture and structural models of the "Revit advanced sample project" combined, and georeferenced in Amsterdam Noord on Cloudflare R2:
    combined_arch_str_bimdf = bpl.read_parquet(
        "https://r2.eu.bedrock.engineer/bimpolars/rvt-advanced-sample/rvt-advanced-sample-combined-arch-str-bdf.parquet"
    )
    combined_arch_str_bimdf
    return (combined_arch_str_bimdf,)


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


@app.cell(hide_code=True)
def _(
    GeoSpeckleViewer,
    combined_arch_str_bimdf,
    mo,
    osm_ground_map,
    pdok_3d_buildings,
):
    # The model on OpenStreetMap, among the 3D BAG's buildings
    combined_arch_str_viewer = mo.ui.anywidget(
        GeoSpeckleViewer(
            combined_arch_str_bimdf,
            ground_map=osm_ground_map(combined_arch_str_bimdf),
            tilesets=[pdok_3d_buildings(combined_arch_str_bimdf)],
            height=550,
        )
    )
    combined_arch_str_viewer
    return (combined_arch_str_viewer,)


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
def _(combined_arch_str_bimdf, combined_arch_str_viewer, pl):
    # The elements selected in the GeoSpeckleViewer
    selected_elements = combined_arch_str_bimdf.filter(
        pl.col("id").is_in([_obj["applicationId"] for _obj in combined_arch_str_viewer.value["selected"]])
    )
    selected_elements
    return (selected_elements,)


if __name__ == "__main__":
    app.run()
