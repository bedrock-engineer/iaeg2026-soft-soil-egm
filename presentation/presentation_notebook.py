# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = [
#     "altair",
#     "anywidget==0.11.0",
#     "bimpolars[speckle]",
#     "h5netcdf==1.8.2",
#     "h5py==3.16.0",
#     "marimo>=0.25.2",
#     "numpy",
#     "polars==2.1.0",
#     "pyarrow",
#     "pyproj==3.8.0",
#     "segno==1.6.6",
#     "specklewidgets",
#     "traitlets==5.16.1",
#     "vl-convert-python",
#     "xarray==2026.9.0",
#     "marimo-studio[deno]==0.4.1"
# ]
#
# [tool.uv.sources]
# bimpolars = { git = "https://github.com/bedrock-engineer/bimpolars" }
# specklewidgets = { git = "https://github.com/bedrock-engineer/specklestuff" }
#
# [tool.marimo-studio]
# default = "slides"
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Presentation

    The outputs of the IAEG 2026 talk. The slides themselves are the Reveal.js view in
    `studio/presentation_notebook/slides/`, which places these outputs. The scripts beside this notebook turn
    them into the PowerPoint.
    """)
    return


@app.cell
def _():
    import json
    from pathlib import Path

    import altair as alt
    import anywidget
    import bimpolars as bpl
    import marimo as mo
    import numpy as np
    import polars as pl
    import pyproj
    import segno
    import traitlets
    import xarray as xr
    from specklewidgets import GeoSpeckleViewer
    from specklewidgets.geo import pdok_3d_buildings

    # RD New + NAP to WGS 84 follows RDNAPTRANS2018 only with the NSGI grids, which PROJ fetches
    pyproj.network.set_network_enabled(True)
    return (
        GeoSpeckleViewer,
        Path,
        alt,
        anywidget,
        bpl,
        json,
        mo,
        np,
        pdok_3d_buildings,
        pl,
        segno,
        traitlets,
        xr,
    )


@app.cell
def inputs(Path, bpl, json, mo, pl):
    PRESENTATION = Path(mo.notebook_dir())
    NOTEBOOKS = PRESENTATION.parent / "notebooks"
    DATA_DIR = PRESENTATION.parent / "data"
    # The simulation run the talk shows, one of the runs 04_simulation.py saves
    RUN_FILE = DATA_DIR / "simulations" / "qc-fs_d9e811b2d185.nc"
    SITE_URL = "https://bedrock-engineer.github.io/iaeg2026-soft-soil-egm/"
    NAVY = "#1b1464"
    # Chart text that reads from the back of the room
    FONT = 20

    DOMAIN_COLORS = json.loads((NOTEBOOKS / "simulation_domains.json").read_text(encoding="utf-8"))["colors"]
    all_samples = pl.read_parquet(DATA_DIR / "sample_domains.parquet")
    samples = all_samples.filter(pl.col("domain").is_not_null())
    geotop_bimdf = bpl.read_parquet(DATA_DIR / "geotop_bimdf.parquet")
    return (
        DOMAIN_COLORS,
        FONT,
        NAVY,
        NOTEBOOKS,
        PRESENTATION,
        RUN_FILE,
        SITE_URL,
        all_samples,
        geotop_bimdf,
        samples,
    )


@app.cell
def run(RUN_FILE, json, np, xr):
    # The run on its grid: the realizations of qc and the statistics per cell as z × y × x
    with xr.open_dataset(RUN_FILE, engine="h5netcdf") as _dataset:
        run_grid = _dataset[["qc", "qc_p10", "qc_p50", "qc_p90", "domain"]].load()
        run_names = _dataset["domain"].attrs["flag_meanings"].split()
        run_definition = json.loads(_dataset.attrs["definition"])
    run_cells = np.nonzero(run_grid["domain"].fillna(-1).values >= 0)
    return run_cells, run_definition, run_grid, run_names


@app.cell
def facts_cell(all_samples, pl, run_definition, samples):
    # The numbers on the slides
    _medians = samples.group_by("domain").agg(pl.median("qc"))["qc"]
    facts = {
        "cpts": all_samples["bro_id"].n_unique(),
        "cpt_meters": round(all_samples.height * 0.5),
        "domains": samples["domain"].n_unique(),
        "qc_min": f"{_medians.min():.1f}",
        "qc_max": f"{_medians.max():.0f}",
        "realizations": run_definition["realizations"],
        "horizontal": run_definition["resolution"]["horizontal"],
        "vertical": run_definition["resolution"]["vertical"],
    }
    facts
    return (facts,)


@app.cell(hide_code=True)
def chart_theme_cell(FONT, NAVY):
    def chart_theme(chart):
        return (
            chart.configure_axis(labelFontSize=FONT, titleFontSize=FONT, labelColor=NAVY, titleColor=NAVY, gridColor="#e6e6ef")
            .configure_legend(labelFontSize=FONT, titleFontSize=FONT)
            .configure_title(fontSize=FONT, color=NAVY)
            .configure_view(stroke=None)
        )

    return (chart_theme,)


@app.cell(hide_code=True)
def problem_figure_cell(PRESENTATION, mo):
    problem_figure = mo.image(PRESENTATION / "public" / "egm_in_bim_context.png", width="100%")
    problem_figure
    return (problem_figure,)


@app.cell(hide_code=True)
def data_viewer_cell(GeoSpeckleViewer, geotop_bimdf, mo, pdok_3d_buildings):
    # GeoTOP's voxels among the 3D BAG
    data_viewer = mo.ui.anywidget(GeoSpeckleViewer(geotop_bimdf, tilesets=[pdok_3d_buildings(geotop_bimdf)], height=900))
    data_viewer
    return (data_viewer,)


@app.cell(hide_code=True)
def domains_chart_cell(DOMAIN_COLORS, NAVY, alt, chart_theme, pl, samples):
    # Per domain, from the top down: its CPT samples' qc from P10 to P90, its median and how much data it has
    _summary = (
        samples.filter(pl.col("qc") > 0)
        .group_by("domain")
        .agg(
            p10=pl.col("qc").quantile(0.1),
            p50=pl.col("qc").median(),
            p90=pl.col("qc").quantile(0.9),
            cpts=pl.col("bro_id").n_unique(),
            meters=pl.len() * 0.5,
        )
        .with_columns(label=pl.format("{} · {} CPTs · {} m", "domain", "cpts", pl.col("meters").round(0).cast(pl.Int64)))
    )
    _labels = [_summary.filter(pl.col("domain") == _domain)["label"][0] for _domain in DOMAIN_COLORS]
    _y = alt.Y("label:N", sort=_labels, title=None, axis=alt.Axis(labelLimit=420))
    _color = alt.Color("domain:N", scale=alt.Scale(domain=list(DOMAIN_COLORS), range=list(DOMAIN_COLORS.values())), legend=None)
    _x = alt.X("p10:Q", title="Cone resistance qc, P10 to P90 and median (MPa)", scale=alt.Scale(type="log", domain=[0.1, 100]))
    _bars = alt.Chart(_summary).mark_bar(size=34, stroke=NAVY, strokeWidth=1).encode(x=_x, x2="p90:Q", y=_y, color=_color)
    _medians = alt.Chart(_summary).mark_tick(color=NAVY, size=44, thickness=4).encode(x="p50:Q", y=_y)
    domains_chart = chart_theme((_bars + _medians).properties(width=820, height=520))
    domains_chart
    return (domains_chart,)


@app.cell(hide_code=True)
def cross_sections_widget(NOTEBOOKS, anywidget, traitlets):
    class CrossSections(anywidget.AnyWidget):
        """The cells from above at the level z, with a west–east section through the row of cells at y and a
        south–north one through the column of cells at x; as in 04_simulation.py"""

        _esm = NOTEBOOKS / "cross_sections.js"
        voxels = traitlets.List().tag(sync=True)
        cell = traitlets.Dict().tag(sync=True)
        units = traitlets.List().tag(sync=True)
        lithologies = traitlets.List().tag(sync=True)
        cpts = traitlets.List().tag(sync=True)
        domains = traitlets.List().tag(sync=True)
        domain_of = traitlets.List().tag(sync=True)
        values = traitlets.Bytes().tag(sync=True)
        value_scale = traitlets.Dict().tag(sync=True)
        color_modes = traitlets.List([]).tag(sync=True)
        color_by = traitlets.Unicode("value").tag(sync=True)
        selected_cpt = traitlets.Unicode("").tag(sync=True)
        x = traitlets.Float().tag(sync=True)
        y = traitlets.Float().tag(sync=True)
        z = traitlets.Float().tag(sync=True)

    return (CrossSections,)


@app.cell(hide_code=True)
def section_view_cell(CrossSections, DOMAIN_COLORS, np, pl, run_cells, run_grid, run_names, samples):
    _iz, _iy, _ix = run_cells
    _coords = {_axis: run_grid[_axis].values for _axis in ("x", "y", "z")}
    _size = {
        "x": float(_coords["x"][1] - _coords["x"][0]),
        "y": float(_coords["y"][1] - _coords["y"][0]),
        "z": float(np.abs(_coords["z"][1] - _coords["z"][0])),
    }
    _cells = pl.DataFrame(
        {
            "x": _coords["x"][_ix] - _size["x"] / 2,
            "y": _coords["y"][_iy] - _size["y"] / 2,
            "z": np.round(_coords["z"][_iz], 3),
            "unit": np.zeros(len(_ix), dtype=np.int32),
            "lithology": np.zeros(len(_ix), dtype=np.int32),
        }
    )
    _domain = run_grid["domain"].values[_iz, _iy, _ix].astype(int)
    _cpts = samples.sort("z", descending=True).group_by("bro_id", maintain_order=True).agg(pl.first("x", "y"), "z", "qc")
    # The sections start through the column with the most CPT data, at the samples' median level
    _start = samples.group_by("column_x", "column_y").agg(pl.len()).sort("len", descending=True).row(0)
    section_view = CrossSections(
        voxels=_cells.rows(),
        cell=_size,
        units=[{"code": "", "name": "", "color": "#cccccc"}],
        lithologies=[{"name": "", "color": "#cccccc"}],
        cpts=_cpts.to_dicts(),
        domains=[{"name": _name, "color": DOMAIN_COLORS[_name]} for _name in run_names],
        domain_of=_domain.tolist(),
        x=float(_start[0]) + 45,
        y=float(_start[1]) + 45,
        z=float(np.round(_coords["z"][np.abs(_coords["z"] - float(samples["z"].median())).argmin()], 3)),
    )
    return (section_view,)


@app.cell(hide_code=True)
def realization_cell(mo, run_grid):
    # 0: the median; else one realization. The filming script steps through them.
    realization = mo.ui.slider(0, int(run_grid.sizes["realization"]), value=0, label="Realization (0: the median)", full_width=True)
    realization
    return (realization,)


@app.cell(hide_code=True)
def section_values(np, realization, run_cells, run_grid, section_view):
    # The cross-sections colored by qc: the median, or one realization on the same scale
    _iz, _iy, _ix = run_cells
    _median = run_grid["qc_p50"].values[_iz, _iy, _ix]
    _values = _median if realization.value == 0 else run_grid["qc"].values[realization.value - 1, _iz, _iy, _ix]
    _low, _high = np.nanpercentile(_median, [2, 98])
    section_view.values = np.asarray(_values, dtype=np.float32).tobytes()
    section_view.value_scale = {
        "label": "qc median (MPa)" if realization.value == 0 else f"qc, realization {realization.value} (MPa)",
        "log": True,
        "min": float(_low),
        "max": float(_high),
        "scheme": "viridis",
    }
    section_view.color_by = "value"
    return


@app.cell(hide_code=True, expand_output=True)
def sections(section_view):
    section_view
    return


@app.cell(hide_code=True)
def uncertainty_chart_cell(alt, chart_theme, np, pl, run_grid, samples):
    # The column of cells at the CPT with the most samples: its realizations and its data
    _cpt_id = samples.group_by("bro_id").len().sort("len", descending=True)["bro_id"][0]
    _cpt = samples.filter((pl.col("bro_id") == _cpt_id) & (pl.col("qc") > 0))
    _x, _y = _cpt["x"][0], _cpt["y"][0]
    _column = run_grid.sel(x=_x, y=_y, method="nearest")
    _z = _column["z"].values
    _realizations = pl.DataFrame(
        {
            "z": np.tile(_z, _column.sizes["realization"]),
            "realization": np.repeat(np.arange(_column.sizes["realization"]), len(_z)),
            "qc": _column["qc"].values.ravel(),
        }
    ).drop_nans()
    _scale = alt.Scale(type="log", domain=[0.05, 100])
    _levels = alt.Scale(domain=[-36.5, 1.5])
    _lines = (
        alt.Chart(_realizations)
        .mark_line(strokeWidth=1, opacity=0.6, color="#4c78a8")
        .encode(
            x=alt.X("qc:Q", title="qc (MPa)", scale=_scale),
            y=alt.Y("z:Q", title="Level (m NAP)", scale=_levels),
            detail="realization:N",
            order="z:Q",
        )
    )
    _points = alt.Chart(_cpt.select("z", "qc")).mark_circle(color="black", size=36).encode(x="qc:Q", y="z:Q")

    # P90 / P10 of qc along the west–east section through the same CPT, at 0.5 m in the vertical: rendered
    # outputs are limited to 5 MB
    _section = run_grid.sel(y=_y, method="nearest")
    _section = _section.coarsen(z=round(0.5 / float(abs(_section["z"][1] - _section["z"][0]))), boundary="trim").median()
    _ratio = _section["qc_p90"].values / _section["qc_p10"].values
    _iz, _ix = np.nonzero(np.isfinite(_ratio))
    _size = float(_section["x"].values[1] - _section["x"].values[0])
    _dz = float(abs(_section["z"].values[1] - _section["z"].values[0]))
    _cells = pl.DataFrame(
        {
            "x": _section["x"].values[_ix] - _size / 2,
            "x2": _section["x"].values[_ix] + _size / 2,
            "z": _section["z"].values[_iz] - _dz / 2,
            "z2": _section["z"].values[_iz] + _dz / 2,
            "ratio": _ratio[_iz, _ix],
        }
    )
    _spread = (
        alt.Chart(_cells)
        .mark_rect()
        .encode(
            x=alt.X("x:Q", title="RD x (m)", scale=alt.Scale(zero=False, nice=False), axis=alt.Axis(format="d", tickCount=4)),
            x2="x2:Q",
            y=alt.Y("z:Q", title=None, scale=_levels),
            y2="z2:Q",
            color=alt.Color(
                "ratio:Q",
                title="P90 / P10",
                scale=alt.Scale(scheme="oranges", type="log", domain=[1, 100], clamp=True),
                legend=alt.Legend(gradientLength=380, orient="right"),
            ),
        )
        .properties(width=760, height=500)
    )
    uncertainty_chart = chart_theme(alt.hconcat((_lines + _points).properties(width=320, height=500), _spread))
    uncertainty_chart
    return (uncertainty_chart,)


@app.cell(hide_code=True)
def qr_cell(NAVY, SITE_URL, mo, segno):
    # The QR code on the closing slide
    qr = mo.Html(segno.make(SITE_URL, error="m").svg_inline(scale=8, dark=NAVY))
    qr
    return (qr,)


if __name__ == "__main__":
    app.run()
