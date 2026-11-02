# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair",
#     "anywidget==0.11.0",
#     "bimpolars",
#     "bromodels==0.0.1",
#     "marimo>=0.25.2",
#     "marimo-lens==0.2.4",
#     "numpy",
#     "polars==2.1.0",
#     "pyarrow",
#     "pyproj==3.8.0",
#     "specklewidgets",
#     "traitlets==5.16.1",
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
    mo.md(r"""
    # Simulation domains

    A **simulation domain** is a group of GeoTOP voxels that share one variogram and one set of
    conditioning CPT data. Choose how to group the voxels and see, for each domain, how much of the
    model it fills, how many CPTs condition it and whether its CPT data differ from its neighbors'.

    Reads the BimDataFrame of GeoTOP voxels and the CPT table that `01_get_data.py` writes into
    `data/`.
    """)
    return


@app.cell
def _():
    import json
    from datetime import datetime
    from pathlib import Path

    import altair as alt
    import anywidget
    import bimpolars as bpl
    import bromodels
    import marimo as mo
    import numpy as np
    import polars as pl
    import pyproj
    import traitlets
    from marimo_lens import Lens
    from specklewidgets import GeoSpeckleViewer
    from specklewidgets.bim import bim_objects
    from specklewidgets.geo import pdok_3d_buildings
    from specklewidgets.models import models_gz

    # RD New + NAP to WGS 84 follows RDNAPTRANS2018 only with the NSGI grids, which PROJ fetches
    pyproj.network.set_network_enabled(True)
    # The charts take thousands of CPT samples
    alt.data_transformers.disable_max_rows()
    return (
        GeoSpeckleViewer,
        Lens,
        Path,
        alt,
        anywidget,
        bim_objects,
        bpl,
        bromodels,
        datetime,
        json,
        mo,
        models_gz,
        np,
        pdok_3d_buildings,
        pl,
        traitlets,
    )


@app.cell(hide_code=True)
def _(Lens):
    # marimo-lens: select a region of any output and add a note for the notebook agent
    lens = Lens()
    lens
    return


@app.cell
def inputs(Path, mo):
    DATA_DIR = Path(mo.notebook_dir()).parent / "data"
    # The inputs 01_get_data.py writes: the cells that read them run again when it replaces them
    geotop_parquet = mo.watch.file(DATA_DIR / "geotop_bimdf.parquet")
    cpts_parquet = mo.watch.file(DATA_DIR / "cpts.parquet")
    # The simulation domains this notebook saves, for 03 to read: their definition, committed with the
    # notebooks, and the domain of each voxel and CPT sample, in data/
    DOMAINS_JSON = Path(mo.notebook_dir()) / "simulation_domains.json"
    VOXEL_DOMAINS_PARQUET = DATA_DIR / "voxel_domains.parquet"
    SAMPLE_DOMAINS_PARQUET = DATA_DIR / "sample_domains.parquet"
    # The saved definition: the cells that read it run again when it is saved
    domains_json = mo.watch.file(DOMAINS_JSON)
    return (
        DOMAINS_JSON,
        SAMPLE_DOMAINS_PARQUET,
        VOXEL_DOMAINS_PARQUET,
        cpts_parquet,
        domains_json,
        geotop_parquet,
    )


@app.cell
def read_inputs(Path, bpl, cpts_parquet, geotop_parquet, mo, pl):
    mo.stop(
        not (Path(geotop_parquet).exists() and Path(cpts_parquet).exists()),
        mo.md("Run `01_get_data.py` and download the data first."),
    )
    geotop_bimdf = bpl.read_parquet(Path(geotop_parquet))
    cpts = pl.read_parquet(Path(cpts_parquet))
    # The voxels' GeoTOP values as columns: x and y are the south-west corner of the 100 m column, z the
    # center of the 0.5 m voxel, in RD New + NAP
    voxels = geotop_bimdf.select("id", pl.col("properties").struct.field("GeoTOP").struct.unnest())
    mo.md(f"**{voxels.height} GeoTOP voxels** in {voxels.select('x', 'y').n_unique()} columns, **{cpts['bro_id'].n_unique()} CPTs**.")
    return cpts, geotop_bimdf, voxels


@app.cell(hide_code=True)
def choose_intro(mo):
    mo.md(r"""
    ## Choose the domains

    Start from a preset, then change which domain each stratigraphic unit belongs to, whether the domains
    split by lithology group, and how deep the model is simulated. Each stratigraphic unit is shown in its
    GeoTOP color, with the share of its voxels in each GeoTOP lithology class; hover over the bar for
    the numbers.
    """)
    return


@app.cell(hide_code=True)
def legends(bromodels, pl):
    # GeoTOP's colors per stratigraphic unit and lithology class
    def _colors(legend, code):
        return {
            _row[code]: f"#{int(_row['RED_DEC']):02x}{int(_row['GREEN_DEC']):02x}{int(_row['BLUE_DEC']):02x}"
            for _row in legend.drop_nulls(code).iter_rows(named=True)
        }


    STRAT_COLORS = _colors(pl.from_pandas(bromodels.GeoTop.geotop_stratigraphic_unit()), "STR_UNIT_CD")
    LITH_COLORS = _colors(pl.from_pandas(bromodels.GeoTop.geotop_lithology_class()), "LITHO_CLASS_CD")
    # GeoTOP's lithology classes grouped the way CPTs tell them apart, each group in a typical class's color
    LITH_GROUPS = {"v": "peat", "k": "clay", "kz": "clayey sand", "zf": "sand", "zm": "sand", "zg": "sand", "g": "sand", "a": "fill"}
    LITH_GROUP_COLORS = {_group: LITH_COLORS[_code] for _code, _group in [("v", "peat"), ("k", "clay"), ("kz", "clayey sand"), ("zm", "sand"), ("a", "fill")]}
    return LITH_COLORS, LITH_GROUPS, LITH_GROUP_COLORS, STRAT_COLORS


@app.cell(hide_code=True)
def presets(DOMAINS_JSON, json, mo):
    # The small stratigraphic units pooled with the unit their CPT data match (median qc in MPa):
    # - ANAWA (0.98), the Walcheren channel deposits, into NAWA (1.07)
    # - NAWOVE (13.7), NIBA (13.5), ENAWO (8.9) and BX (8.0) into BXWISIKO (14.3). The CPTs read sand in
    #   all of them: GeoTOP's Laag van Velsen and Basisveen are thinner here than its 0.5 m voxels, and the
    #   Wormer channel deposits and the undivided Boxtel are sandy.
    # The anthropogenic fill (AAOP) is not simulated.
    _POOLED = {
        "ANAWA": "NAWA",
        "NAWOVE": "BXWISIKO",
        "NIBA": "BXWISIKO",
        "ENAWO": "BXWISIKO",
        "BX": "BXWISIKO",
        "AAOP": "not simulated",
    }
    # The saved simulation domains come first, when there are any
    _saved = json.loads(DOMAINS_JSON.read_text(encoding="utf-8")) if DOMAINS_JSON.exists() else None
    _SAVED = "Saved in simulation_domains.json"
    PRESETS = {
        **(
            {
                _SAVED: {
                    "units": _saved["units"],
                    "split": _saved["split_by_lithology"],
                    "base": _saved["simulate_down_to"],
                    "min_meters": _saved["min_cpt_meters"],
                }
            }
            if _saved
            else {}
        ),
        "Every stratigraphic unit": {"units": {}, "split": False, "cut": False},
        "Small stratigraphic units pooled by their CPT data": {"units": _POOLED, "split": False, "cut": False},
        "Pooled stratigraphic units, cut at the deepest CPT": {"units": _POOLED, "split": False, "cut": True},
        "Pooled stratigraphic units, split by lithology group": {"units": _POOLED, "split": True, "cut": False},
        "Lithology groups only": {"units": {"AAOP": "not simulated"}, "all": "all stratigraphic units", "split": True, "cut": False},
    }
    preset = mo.ui.dropdown(
        options=list(PRESETS),
        value=_SAVED if _saved else "Small stratigraphic units pooled by their CPT data",
        label="Start from",
    )
    preset
    return PRESETS, preset


@app.cell(hide_code=True, expand_output=True)
def controls(
    LITH_COLORS,
    PRESETS,
    STRAT_COLORS,
    cpts,
    mo,
    np,
    pl,
    preset,
    voxels,
):
    # The stratigraphic units in the model from the top down, each with the domain the preset puts it in
    _units = (
        voxels.group_by("stratigraphic_unit")
        .agg(
            pl.max("z").alias("top"),
            pl.min("z").alias("base"),
            pl.len().alias("voxels"),
            pl.first("geologische_eenheid"),
        )
        .sort("top", descending=True)
    )
    _preset = PRESETS[preset.value]
    _options = [
        *_units["stratigraphic_unit"],
        "all stratigraphic units",
        "not simulated",
    ]
    unit_domains = mo.ui.dictionary(
        {
            _unit: mo.ui.dropdown(
                _options,
                value=_preset["units"].get(_unit, _preset.get("all", _unit)),
            )
            for _unit in _units["stratigraphic_unit"]
        }
    )
    split_by_lithology = mo.ui.switch(
        value=_preset["split"], label="Split each domain by lithology group"
    )
    # Below the deepest CPT reading no CPT conditions a voxel
    _deepest_cpt = float(np.floor(cpts["z"].min() * 2) / 2)
    base_cut = mo.ui.slider(
        start=-50,
        stop=0,
        step=1,
        value=_preset.get("base", _deepest_cpt if _preset.get("cut") else -50),
        include_input=True,
        label="Simulate down to (m NAP)",
    )
    min_meters = mo.ui.slider(
        start=0.5,
        stop=5,
        step=0.5,
        value=_preset.get("min_meters", 1),
        show_value=True,
        label="A CPT conditions a domain with at least (m)",
    )

    def _text_color(hex_color):
        # Dark text on light colors, white on dark ones
        _r, _g, _b = (int(hex_color[_i : _i + 2], 16) for _i in (1, 3, 5))
        return (
            "black" if 0.299 * _r + 0.587 * _g + 0.114 * _b > 140 else "white"
        )

    def _colored(text, color):
        return f'<td style="background:{color};color:{_text_color(color)};padding:2px 6px">{text}</td>'

    # Each stratigraphic unit's voxels per GeoTOP lithology class, as a bar of the classes' colors
    _lithology = (
        voxels.group_by("stratigraphic_unit", "lithoklasse", "grondsoort")
        .len()
        .sort("len", descending=True)
    )

    def _lithology_bar(unit):
        _rows = _lithology.filter(pl.col("stratigraphic_unit") == unit)
        _total = _rows["len"].sum()
        _segments = "".join(
            f'<div title="{_r["grondsoort"]}: {_r["len"]} voxels, {100 * _r["len"] / _total:.0f} %" '
            f'style="width:{100 * _r["len"] / _total}%;background:{LITH_COLORS[_r["lithoklasse"]]}"></div>'
            for _r in _rows.iter_rows(named=True)
        )
        return f'<div style="display:flex;width:160px;height:16px;border:1px solid #999">{_segments}</div>'

    _rows = "".join(
        "<tr>"
        + _colored(
            _r["stratigraphic_unit"], STRAT_COLORS[_r["stratigraphic_unit"]]
        )
        + _colored(
            _r["geologische_eenheid"], STRAT_COLORS[_r["stratigraphic_unit"]]
        )
        + f'<td style="text-align:right;padding:2px 6px">{_r["top"]:+.1f}</td>'
        + f'<td style="text-align:right;padding:2px 6px">{_r["base"]:+.1f}</td>'
        + f'<td style="text-align:right;padding:2px 6px">{_r["voxels"]}</td>'
        + f'<td style="padding:2px 6px">{_lithology_bar(_r["stratigraphic_unit"])}</td>'
        + f'<td style="padding:2px 6px">{unit_domains[_r["stratigraphic_unit"]]}</td>'
        + "</tr>"
        for _r in _units.iter_rows(named=True)
    )
    _header = "".join(
        f'<th style="text-align:left;padding:2px 6px;white-space:nowrap">{_h}</th>'
        for _h in [
            "Code",
            "Stratigraphic unit",
            "Top (m NAP)",
            "Base (m NAP)",
            "No. voxels",
            "Lithology classes",
            "Simulation domain",
        ]
    )
    # The lithology classes in the model, from the most voxels to the fewest
    _classes = (
        _lithology.group_by("lithoklasse", "grondsoort")
        .agg(pl.sum("len"))
        .sort("len", descending=True)
    )
    _legend = " ".join(
        f'<span style="white-space:nowrap;margin-right:12px">'
        f'<span style="display:inline-block;width:12px;height:12px;background:{LITH_COLORS[_r["lithoklasse"]]};'
        f'vertical-align:middle;margin-right:4px"></span>{_r["grondsoort"]}</span>'
        for _r in _classes.iter_rows(named=True)
    )
    mo.vstack(
        [
            mo.hstack(
                [split_by_lithology, base_cut, min_meters],
                justify="start",
                gap=2,
            ),
            mo.md(f"The deepest CPT reading is at {_deepest_cpt:+.1f} m NAP."),
            mo.Html(
                f'<table style="border-collapse:separate;border-spacing:0 2px"><tr>{_header}</tr>{_rows}</table>'
            ),
            mo.Html(
                f'<div style="font-size:0.85em">Lithology classes: {_legend}</div>'
            ),
        ]
    )
    return base_cut, min_meters, split_by_lithology, unit_domains


@app.cell
def samples(cpts, pl, voxels):
    # CPT readings averaged per voxel they pass through: the column from x and y (its south-west corner),
    # the 0.5 m level from the nearest voxel center
    samples = (
        cpts.with_columns(
            column_x=pl.col("x") // 100 * 100,
            column_y=pl.col("y") // 100 * 100,
            voxel_z=(pl.col("z") * 2).round() / 2,
        )
        .group_by("bro_id", "column_x", "column_y", "voxel_z")
        .agg(pl.first("x", "y"), pl.median("qc", "fs", "rf"), pl.len().alias("readings"))
        .join(
            voxels.select(
                pl.col("x").alias("column_x"), pl.col("y").alias("column_y"), pl.col("z").alias("voxel_z"),
                "stratigraphic_unit", "lithoklasse", "grondsoort",
            ),
            on=["column_x", "column_y", "voxel_z"],
        )
        .rename({"voxel_z": "z"})
    )
    return (samples,)


@app.cell
def domains(
    LITH_GROUPS,
    LITH_GROUP_COLORS,
    STRAT_COLORS,
    alt,
    base_cut,
    pl,
    samples,
    split_by_lithology,
    unit_domains,
    voxels,
):
    # Each voxel's domain from the controls; null where it is not simulated
    _lith_group = pl.col("lithoklasse").replace_strict(LITH_GROUPS, default="other")
    _unit_domain = pl.col("stratigraphic_unit").replace_strict(unit_domains.value)
    if split_by_lithology.value:
        _domain = (
            pl.when(_unit_domain == "all stratigraphic units")
            .then(_lith_group)
            .otherwise(pl.concat_str([_unit_domain, _lith_group], separator=" · "))
        )
    else:
        _domain = _unit_domain
    DOMAIN = pl.when((_unit_domain != "not simulated") & (pl.col("z") >= base_cut.value)).then(_domain).alias("domain")

    voxel_domains = voxels.with_columns(DOMAIN)
    sample_domains = samples.with_columns(DOMAIN).drop_nulls("domain")

    # The domains from the top down, in GeoTOP's color where a domain is one stratigraphic unit or one lithology group
    _TABLEAU20 = [
        "#4e79a7", "#a0cbe8", "#f28e2b", "#ffbe7d", "#59a14f", "#8cd17d", "#b6992d", "#f1ce63", "#499894", "#86bcb6",
        "#e15759", "#ff9d9a", "#79706e", "#bab0ac", "#d37295", "#fabfd2", "#b07aa1", "#d4a6c8", "#9d7660", "#d7b5a6",
    ]
    _domains = voxel_domains.drop_nulls("domain").group_by("domain").agg(pl.max("z")).sort("z", descending=True)["domain"]
    DOMAIN_COLORS = {
        _d: STRAT_COLORS.get(_d) or LITH_GROUP_COLORS.get(_d) or _TABLEAU20[_i % len(_TABLEAU20)]
        for _i, _d in enumerate(_domains)
    }
    domain_scale = alt.Scale(domain=list(DOMAIN_COLORS), range=list(DOMAIN_COLORS.values()))
    return DOMAIN_COLORS, domain_scale, sample_domains, voxel_domains


@app.cell
def domain_summary(
    DOMAIN_COLORS,
    min_meters,
    pl,
    sample_domains,
    voxel_domains,
):
    _per_cpt = sample_domains.group_by("domain", "bro_id").agg((pl.len() * 0.5).alias("meters"))
    domain_summary = (
        voxel_domains.drop_nulls("domain")
        .group_by("domain")
        .agg(
            pl.max("z").alias("top (m NAP)"),
            pl.min("z").alias("base (m NAP)"),
            pl.len().alias("voxels"),
            (100 * pl.len() / voxel_domains.height).round(1).alias("% of model"),
        )
        .join(
            _per_cpt.group_by("domain").agg(
                (pl.col("meters") >= min_meters.value).sum().alias("CPTs"),
                pl.sum("meters").alias("CPT meters"),
            ),
            on="domain",
            how="left",
        )
        .join(
            sample_domains.group_by("domain").agg(
                pl.median("qc").round(2).alias("median qc (MPa)"),
                (pl.col("qc").log10().quantile(0.75) - pl.col("qc").log10().quantile(0.25)).round(2).alias("IQR log₁₀ qc"),
                pl.median("rf").round(2).alias("median Rf (%)"),
            ),
            on="domain",
            how="left",
        )
        .with_columns(pl.col("CPTs", "CPT meters").fill_null(0))
        .with_columns(
            variogram=pl.when(pl.col("CPTs") >= 20)
            .then(pl.lit("horizontal and vertical"))
            .when(pl.col("CPTs") >= 5)
            .then(pl.lit("vertical only, or borrowed"))
            .otherwise(pl.lit("too few CPTs: pool or skip")),
            color=pl.col("domain").replace_strict(DOMAIN_COLORS),
        )
        .sort("top (m NAP)", descending=True)
        .select("color", "domain", pl.all().exclude("color", "domain"))
    )
    return (domain_summary,)


@app.cell(hide_code=True)
def domain_table(domain_summary, min_meters, mo, voxel_domains):
    _not_simulated = voxel_domains["domain"].null_count()
    mo.vstack(
        [
            mo.md(
                f"## 1 · {domain_summary.height} domains\n\n"
                f"{100 * _not_simulated / voxel_domains.height:.1f} % of the voxels are not simulated. "
                f"A domain needs about 20 CPTs for a horizontal and a vertical variogram, and 5 for a vertical one; "
                f"a CPT counts for a domain with at least {min_meters.value} m in it."
            ),
            mo.ui.table(
                domain_summary,
                selection=None,
                style_cell=lambda _row, column, value: {"backgroundColor": value, "color": value} if column == "color" else {},
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def coverage(alt, domain_scale, domain_summary, min_meters, pl):
    # How much of the model each domain fills, and how many CPTs condition it
    _order = domain_summary["domain"].to_list()
    _base = alt.Chart(domain_summary).encode(
        y=alt.Y("domain:N", sort=_order, title=None),
        color=alt.Color("domain:N", scale=domain_scale, legend=None),
        tooltip=["domain", "voxels", "% of model", "CPTs", "CPT meters", "variogram"],
    )
    _share = _base.mark_bar().encode(x=alt.X("% of model:Q", title="Share of the model (%)")).properties(width=260)
    # The CPTs a domain needs for a vertical variogram (5) and for a horizontal one too (20), labeled
    # one above the other
    _thresholds = pl.DataFrame({"CPTs": [5, 20], "label": ["5: vertical variogram", "20: horizontal and vertical"]})
    _rules = alt.Chart(_thresholds).mark_rule(strokeDash=[4, 3], color="#555").encode(x="CPTs:Q")
    _labels = [
        alt.Chart(_thresholds[[_i]])
        .mark_text(align="left", dx=3, dy=_dy, color="#555", fontSize=10)
        .encode(x="CPTs:Q", y=alt.value(0), text="label:N")
        for _i, _dy in [(0, -18), (1, -6)]
    ]
    _cpts = alt.layer(
        _base.mark_bar().encode(x=alt.X("CPTs:Q", title=f"CPTs with at least {min_meters.value} m in the domain")),
        _rules,
        *_labels,
    ).properties(width=320)
    alt.hconcat(_share, _cpts).resolve_scale(y="shared")
    return


@app.cell(hide_code=True)
def section_intro(mo):
    mo.md(r"""
    ## 3 · Cross-sections

    The voxels from above at one level, with a west–east section above and a south–north section to
    the right, both through the column under the red dot. Drag the red dot in the plan to move the
    sections, and drag in either section to change the plan's level. The CPTs are dots in the plan. In
    the sections, each column they cross shows the median qc of its CPTs, in a band from their 10th to
    their 90th percentile. Hover over a CPT in the plan for its own qc, and over a voxel for its domain,
    stratigraphic unit and lithology class.
    """)
    return


@app.cell(hide_code=True)
def cross_sections_widget(Path, anywidget, mo, traitlets):
    class CrossSections(anywidget.AnyWidget):
        """The voxels from above at the level z, with a west–east section through the row of columns at
        y and a south–north one through the column at x (x and y a column's south-west corner)"""

        _esm = Path(mo.notebook_dir()) / "cross_sections.js"
        # Per voxel: x, y, z and its indices in units and lithologies, which hold each stratigraphic
        # unit's code, name and color and each lithology class's name and color
        voxels = traitlets.List().tag(sync=True)
        units = traitlets.List().tag(sync=True)
        lithologies = traitlets.List().tag(sync=True)
        # Per CPT: its x and y, and its qc (MPa) per voxel level z
        cpts = traitlets.List().tag(sync=True)
        # The domains' names and colors, and each voxel's index in them (-1 where it is not simulated)
        domains = traitlets.List().tag(sync=True)
        domain_of = traitlets.List().tag(sync=True)
        # What the voxels are colored by: "domain", "unit" or "lithology"
        color_by = traitlets.Unicode("domain").tag(sync=True)
        x = traitlets.Float().tag(sync=True)
        y = traitlets.Float().tag(sync=True)
        z = traitlets.Float().tag(sync=True)

    return (CrossSections,)


@app.cell(hide_code=True, expand_output=True)
def cross_sections(
    CrossSections,
    LITH_COLORS,
    STRAT_COLORS,
    mo,
    pl,
    samples,
    voxels,
):
    # Made once for the voxels, so the sections stay where they were dragged when the domains change
    # The stratigraphic units from the top down and the lithology classes from the most voxels to the
    # fewest, in GeoTOP's colors
    _units = (
        voxels.group_by("stratigraphic_unit")
        .agg(pl.max("z"), pl.first("geologische_eenheid"))
        .sort("z", descending=True)
        .select(
            code="stratigraphic_unit",
            name=pl.format("{} · {}", "stratigraphic_unit", "geologische_eenheid"),
            color=pl.col("stratigraphic_unit").replace_strict(STRAT_COLORS),
        )
    )
    _lithologies = (
        voxels.group_by("grondsoort")
        .agg(pl.len(), pl.first("lithoklasse"))
        .sort("len", descending=True)
        .select(name="grondsoort", color=pl.col("lithoklasse").replace_strict(LITH_COLORS))
    )
    _cpts = samples.sort("z", descending=True).group_by("bro_id", maintain_order=True).agg(pl.first("x", "y"), "z", "qc")
    # The sections start through the column with the most CPTs, at the CPT samples' median level
    _start = samples.group_by("column_x", "column_y").agg(pl.n_unique("bro_id")).sort("bro_id", descending=True).row(0)
    section_view = CrossSections(
        voxels=voxels.select(
            pl.col("x", "y").cast(pl.Int64),
            "z",
            pl.col("stratigraphic_unit").replace_strict({_u: _i for _i, _u in enumerate(_units["code"])}),
            pl.col("grondsoort").replace_strict({_l: _i for _i, _l in enumerate(_lithologies["name"])}),
        ).rows(),
        units=_units.to_dicts(),
        lithologies=_lithologies.to_dicts(),
        cpts=_cpts.to_dicts(),
        x=_start[0],
        y=_start[1],
        z=round(samples["z"].median() * 2) / 2,
    )
    cross_sections = mo.ui.anywidget(section_view)
    cross_sections
    return cross_sections, section_view


@app.cell(hide_code=True, expand_output=True)
def domain_viewer(GeoSpeckleViewer, geotop_bimdf, mo, pdok_3d_buildings):
    # Made once, so it keeps its camera and its WebGL context; domain_viewer_objects fills it
    speckle_view = GeoSpeckleViewer(tilesets=[pdok_3d_buildings(geotop_bimdf)], height=525)
    domain_viewer = mo.ui.anywidget(speckle_view)
    cut_sections = mo.ui.switch(value=True, label="Leave out the voxels the cross-sections run through")
    mo.vstack([cut_sections, domain_viewer])
    return cut_sections, domain_viewer, speckle_view


@app.cell(hide_code=True)
def domain_viewer_objects(
    DOMAIN_COLORS,
    LITH_COLORS,
    STRAT_COLORS,
    bim_objects,
    bpl,
    cpt_sticks,
    cross_sections,
    cut_sections,
    models_gz,
    pl,
    speckle_view,
    styled_bimdf,
    voxel_bimdf,
):
    # The voxels into the 3D viewer, colored like the cross-sections: by simulation domain (the simulated
    # voxels only), stratigraphic unit or lithology class. With cut_sections on, without the voxels in
    # the cross-sections' row and column of columns.
    _color_by = cross_sections.value["color_by"]
    if _color_by == "unit":
        _voxels = styled_bimdf(voxel_bimdf, "stratigraphic_unit", pl.col("stratigraphic_unit").replace_strict(STRAT_COLORS))
    elif _color_by == "lithology":
        _voxels = styled_bimdf(voxel_bimdf, "grondsoort", pl.col("lithoklasse").replace_strict(LITH_COLORS))
    else:
        _voxels = styled_bimdf(
            voxel_bimdf.filter(pl.col("domain").is_not_null()), "domain", pl.col("domain").replace_strict(DOMAIN_COLORS)
        )
    if cut_sections.value:
        _geotop = pl.col("properties").struct.field("GeoTOP")
        _voxels = _voxels.filter(
            (_geotop.struct.field("x") != cross_sections.value["x"]) & (_geotop.struct.field("y") != cross_sections.value["y"])
        )
    viewer_bimdf = bpl.concat([_voxels, cpt_sticks], how="diagonal_relaxed")
    speckle_view.objects_gz = models_gz(bim_objects(viewer_bimdf))
    return (viewer_bimdf,)


@app.cell(hide_code=True)
def viewer_selection(domain_viewer, pl, viewer_bimdf):
    # The voxels and CPTs selected in the GeoSpeckleViewer
    viewer_bimdf.filter(
        pl.col("id").is_in([_obj["applicationId"] for _obj in domain_viewer.value["selected"]])
    ).select("id", "class", "name", "domain", "stratigraphic_unit", "grondsoort")
    return


@app.cell(hide_code=True)
def cross_sections_domains(DOMAIN_COLORS, section_view, voxel_domains):
    # The domains into the cross-sections, without making them again
    section_view.domains = [{"name": _name, "color": _color} for _name, _color in DOMAIN_COLORS.items()]
    section_view.domain_of = (
        voxel_domains["domain"].replace_strict(list(DOMAIN_COLORS), range(len(DOMAIN_COLORS)), default=-1).fill_null(-1).to_list()
    )
    return


@app.cell
def voxel_bimdf(bpl, cpts, geotop_bimdf, pl, voxel_domains):
    def styled_bimdf(bimdf, name, color):
        """The elements with the column name as their class, each mesh in one color: color, an
        expression of "#rrggbb" strings"""
        _rgba = pl.concat_list(
            [color.str.slice(_i, 2).str.to_integer(base=16) / 255 for _i in (1, 3, 5)] + [pl.lit(1.0)]
        ).list.to_array(4)
        return bimdf.with_columns(
            pl.col(name).cast(pl.String).cast(pl.Categorical).alias("class"),
            mesh=pl.struct(
                vertices=pl.col("mesh").struct.field("vertices"),
                faces=pl.col("mesh").struct.field("faces"),
                styles=pl.concat_list(pl.struct(name=pl.col(name), rgba=_rgba, face_count=pl.lit(12, dtype=pl.UInt32))),
            ).cast(bpl.MESH_DTYPE),
        )


    # The voxels with their domain, stratigraphic unit and lithology class as columns
    voxel_bimdf = geotop_bimdf.with_columns(
        *voxel_domains.select("domain", "stratigraphic_unit", "lithoklasse", "grondsoort").get_columns()
    )

    # The CPTs as 2 m square sticks from their top to their base, built in RD New + NAP and moved into the
    # voxels' site CRS
    _half = 1.0
    # The same box triangles as the voxels'
    _box_faces = geotop_bimdf["mesh"][0]["faces"]
    _cpt_rows = cpts.group_by("bro_id").agg(pl.first("x", "y"), pl.max("z").alias("top"), pl.min("z").alias("base"))
    _x0, _x1 = pl.col("x") - _half, pl.col("x") + _half
    _y0, _y1 = pl.col("y") - _half, pl.col("y") + _half
    _z0, _z1 = pl.col("base"), pl.col("top")
    cpt_sticks = bpl.to_crs(
        bpl.BimDataFrame(
            _cpt_rows.select(
                id=pl.col("bro_id"),
                name=pl.col("bro_id"),
                **{"class": pl.lit("CPT").cast(pl.Categorical)},
                mesh=pl.struct(
                    vertices=pl.concat_list(
                        _x0, _y0, _z0, _x1, _y0, _z0, _x1, _y1, _z0, _x0, _y1, _z0,
                        _x0, _y0, _z1, _x1, _y0, _z1, _x1, _y1, _z1, _x0, _y1, _z1,
                    ),
                    faces=pl.lit(_box_faces, dtype=pl.List(pl.UInt32)),
                    styles=pl.concat_list(
                        pl.struct(name=pl.lit("CPT"), rgba=pl.lit([0.15, 0.15, 0.15, 1.0]).list.to_array(4), face_count=pl.lit(12, dtype=pl.UInt32))
                    ),
                ).cast(bpl.MESH_DTYPE),
                bbox=pl.struct(xmin=_x0, ymin=_y0, zmin=_z0, xmax=_x1, ymax=_y1, zmax=_z1),
            ),
            crs="EPSG:7415",
        ),
        geotop_bimdf.crs,
    )
    return cpt_sticks, styled_bimdf, voxel_bimdf


@app.cell(hide_code=True)
def separation_intro(mo):
    mo.md(r"""
    ## 4 · Do the domains separate the CPT data?

    The 0.5 m CPT samples per domain, from the softest to the stiffest. Domains are useful when their
    boxes differ from their neighbors' and are narrow inside. Click a domain in the legend of the qc–Rf
    plot to pick it out.
    """)
    return


@app.cell(hide_code=True)
def separation(alt, domain_scale, domain_summary, pl, sample_domains):
    _order = domain_summary.sort("median qc (MPa)")["domain"].to_list()
    _base = alt.Chart(sample_domains.with_columns(pl.col("rf").clip(0, 10))).encode(
        y=alt.Y("domain:N", sort=_order, title=None),
        color=alt.Color("domain:N", scale=domain_scale, legend=None),
    )
    _qc = _base.mark_boxplot(extent="min-max", size=14).encode(
        x=alt.X("qc:Q", scale=alt.Scale(type="log"), title="qc (MPa)")
    ).properties(width=330)
    _rf = _base.mark_boxplot(extent="min-max", size=14).encode(
        x=alt.X("rf:Q", title="Rf (%), clipped at 10")
    ).properties(width=250)
    alt.hconcat(_qc, _rf).resolve_scale(y="shared")
    return


@app.cell(hide_code=True)
def qc_rf(alt, domain_scale, pl, sample_domains):
    _pick = alt.selection_point(fields=["domain"], bind="legend")
    (
        alt.Chart(sample_domains.with_columns(pl.col("rf").clip(0, 10)))
        .mark_circle(size=12)
        .encode(
            x=alt.X("rf:Q", title="Rf (%), clipped at 10"),
            y=alt.Y("qc:Q", scale=alt.Scale(type="log"), title="qc (MPa)"),
            color=alt.Color("domain:N", scale=domain_scale, title="Domain"),
            opacity=alt.condition(_pick, alt.value(0.6), alt.value(0.04)),
            tooltip=["domain", "bro_id", "z", "qc", "rf", "grondsoort"],
        )
        .add_params(_pick)
        .properties(width=520, height=380, title="qc against Rf, one dot per 0.5 m of CPT")
    )
    return


@app.cell(hide_code=True)
def save_intro(mo):
    mo.md(r"""
    ## 5 · Save the simulation domains

    Saving pins the domains chosen above for the next notebooks. It writes their definition to
    `notebooks/simulation_domains.json`, which is committed with the notebooks and comes back here as the
    first preset, and the domain of each voxel and CPT sample to `data/voxel_domains.parquet` and
    `data/sample_domains.parquet`, which `03` reads.
    """)
    return


@app.cell(hide_code=True)
def domain_definition(
    DOMAIN_COLORS,
    LITH_GROUPS,
    base_cut,
    min_meters,
    mo,
    split_by_lithology,
    unit_domains,
):
    # The chosen simulation domains as simulation_domains.json holds them
    domain_definition = {
        "units": dict(unit_domains.value),
        "split_by_lithology": split_by_lithology.value,
        "lithology_groups": LITH_GROUPS,
        "simulate_down_to": base_cut.value,
        "min_cpt_meters": min_meters.value,
        "colors": DOMAIN_COLORS,
    }
    save_domains = mo.ui.run_button(label="Save these simulation domains")
    save_domains
    return domain_definition, save_domains


@app.cell(hide_code=True)
def saved_status(Path, domain_definition, domains_json, json, mo):
    # Whether the saved simulation domains are the ones chosen above; runs again when they are saved
    if not Path(domains_json).exists():
        _status = mo.callout(mo.md("No simulation domains are saved yet."), kind="warn")
    else:
        _saved = json.loads(Path(domains_json).read_text(encoding="utf-8"))
        _saved_at = _saved.pop("saved")
        _status = (
            mo.callout(mo.md(f"The simulation domains above are the ones saved on {_saved_at}."), kind="success")
            if _saved == json.loads(json.dumps(domain_definition))
            else mo.callout(
                mo.md(f"The simulation domains above differ from the ones saved on {_saved_at}. Save them to use them in `03`."),
                kind="warn",
            )
        )
    _status
    return


@app.cell(hide_code=True)
def save(
    DOMAINS_JSON,
    SAMPLE_DOMAINS_PARQUET,
    VOXEL_DOMAINS_PARQUET,
    datetime,
    domain_definition,
    json,
    mo,
    sample_domains,
    save_domains,
    voxel_domains,
):
    mo.stop(not save_domains.value)
    DOMAINS_JSON.write_text(
        json.dumps({"saved": datetime.now().isoformat(timespec="seconds"), **domain_definition}, indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    voxel_domains.write_parquet(VOXEL_DOMAINS_PARQUET)
    sample_domains.write_parquet(SAMPLE_DOMAINS_PARQUET)
    return


if __name__ == "__main__":
    app.run()
