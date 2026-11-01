# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair",
#     "bimpolars",
#     "bromodels==0.0.1",
#     "marimo>=0.25.2",
#     "marimo-lens==0.2.4",
#     "numpy",
#     "polars==2.1.0",
#     "pyarrow",
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


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Simulation domains

    A **simulation domain** is a group of GeoTOP voxels that share one variogram and one set of
    conditioning CPT data. Choose how to group the voxels and see, for each domain, how much of the
    model it fills, how many CPTs condition it and whether its CPT data differ from its neighbours'.

    Reads the BimDataFrame of GeoTOP voxels and the CPT table that `01_get_data.py` writes into
    `data/`.
    """)
    return


@app.cell
def _():
    from pathlib import Path

    import altair as alt
    import bimpolars as bpl
    import bromodels
    import marimo as mo
    import numpy as np
    import polars as pl
    import pyproj
    from marimo_lens import Lens
    from specklewidgets import GeoSpeckleViewer
    from specklewidgets.geo import pdok_3d_buildings

    # RD New + NAP to WGS 84 follows RDNAPTRANS2018 only with the NSGI grids, which PROJ fetches
    pyproj.network.set_network_enabled(True)
    # The charts take thousands of CPT samples
    alt.data_transformers.disable_max_rows()
    return (
        GeoSpeckleViewer,
        Lens,
        Path,
        alt,
        bpl,
        bromodels,
        mo,
        np,
        pdok_3d_buildings,
        pl,
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
    return cpts_parquet, geotop_parquet


@app.cell
def read_inputs(Path, bpl, cpts_parquet, geotop_parquet, mo, pl):
    mo.stop(
        not (Path(geotop_parquet).exists() and Path(cpts_parquet).exists()),
        mo.md("Run `01_get_data.py` and download the data first."),
    )
    geotop_bimdf = bpl.read_parquet(Path(geotop_parquet))
    cpts = pl.read_parquet(Path(cpts_parquet))
    # The voxels' GeoTOP values as columns: x and y are the south-west corner of the 100 m column, z the
    # centre of the 0.5 m voxel, in RD New + NAP
    voxels = geotop_bimdf.select("id", pl.col("properties").struct.field("GeoTOP").struct.unnest())
    mo.md(f"**{voxels.height} GeoTOP voxels** in {voxels.select('x', 'y').n_unique()} columns, **{cpts['bro_id'].n_unique()} CPTs**.")
    return cpts, geotop_bimdf, voxels


@app.cell(hide_code=True)
def choose_intro(mo):
    mo.md(r"""
    ## Choose the domains

    Start from a preset, then change which domain each GeoTOP unit belongs to, whether the domains split
    by lithology, and how deep the model is simulated.
    """)
    return


@app.cell(hide_code=True)
def legends(bromodels, pl):
    # GeoTOP's colours per stratigraphic unit and lithology class
    def _colors(legend, code):
        return {
            _row[code]: f"#{int(_row['RED_DEC']):02x}{int(_row['GREEN_DEC']):02x}{int(_row['BLUE_DEC']):02x}"
            for _row in legend.drop_nulls(code).iter_rows(named=True)
        }


    STRAT_COLORS = _colors(pl.from_pandas(bromodels.GeoTop.geotop_stratigraphic_unit()), "STR_UNIT_CD")
    _lith_colors = _colors(pl.from_pandas(bromodels.GeoTop.geotop_lithology_class()), "LITHO_CLASS_CD")
    # GeoTOP's lithology classes grouped the way CPTs tell them apart, each group in a typical class's colour
    LITH_GROUPS = {"v": "peat", "k": "clay", "kz": "clayey sand", "zf": "sand", "zm": "sand", "zg": "sand", "g": "sand", "a": "fill"}
    LITH_GROUP_COLORS = {_group: _lith_colors[_code] for _code, _group in [("v", "peat"), ("k", "clay"), ("kz", "clayey sand"), ("zm", "sand"), ("a", "fill")]}
    return LITH_GROUPS, LITH_GROUP_COLORS, STRAT_COLORS


@app.cell(hide_code=True)
def presets(mo):
    # Thin units and channel deposits pooled into the main unit they belong to; no fill simulated
    _POOLED = {"ANAWA": "NAWA", "ENAWO": "NAWO", "NAWOVE": "NAWO", "BX": "BXWISIKO", "NIBA": "NIHO", "AAOP": "not simulated"}
    PRESETS = {
        "Every GeoTOP unit": {"units": {}, "split": False, "cut": False},
        "Main units, thin units and channels pooled": {"units": _POOLED, "split": False, "cut": False},
        "Main units, cut at the deepest CPT": {"units": _POOLED, "split": False, "cut": True},
        "Main units split by lithology": {"units": _POOLED, "split": True, "cut": False},
        "Lithology only": {"units": {"AAOP": "not simulated"}, "all": "all units", "split": True, "cut": False},
    }
    preset = mo.ui.dropdown(options=list(PRESETS), value="Main units, thin units and channels pooled", label="Start from")
    preset
    return PRESETS, preset


@app.cell(hide_code=True)
def controls(PRESETS, cpts, mo, np, pl, preset, voxels):
    # The units in the model from the top down, each with the domain the preset puts it in
    _units = (
        voxels.group_by("stratigraphic_unit")
        .agg(pl.max("z").alias("top"), pl.len().alias("voxels"), pl.first("geologische_eenheid"))
        .sort("top", descending=True)
    )
    _preset = PRESETS[preset.value]
    _options = [*_units["stratigraphic_unit"], "all units", "not simulated"]
    unit_domains = mo.ui.dictionary(
        {
            _unit: mo.ui.dropdown(_options, value=_preset["units"].get(_unit, _preset.get("all", _unit)))
            for _unit in _units["stratigraphic_unit"]
        }
    )
    split_by_lithology = mo.ui.switch(value=_preset["split"], label="Split each domain by lithology")
    # Below the deepest CPT reading no CPT conditions a voxel
    _deepest_cpt = float(np.floor(cpts["z"].min() * 2) / 2)
    base_cut = mo.ui.slider(
        start=-50, stop=0, step=0.5, value=_deepest_cpt if _preset["cut"] else -50, show_value=True,
        label="Simulate down to (m NAP)",
    )
    min_metres = mo.ui.slider(start=0.5, stop=5, step=0.5, value=1, show_value=True, label="A CPT conditions a domain with at least (m)")

    _rows = "\n".join(
        f"| {_r['stratigraphic_unit']} | {_r['geologische_eenheid']} | {_r['top']:+.1f} | {_r['voxels']} | {unit_domains[_r['stratigraphic_unit']]} |"
        for _r in _units.iter_rows(named=True)
    )
    mo.hstack(
        [
            mo.md("| Unit | GeoTOP unit | Top (m NAP) | Voxels | Domain |\n|---|---|--:|--:|---|\n" + _rows),
            mo.vstack([split_by_lithology, base_cut, min_metres, mo.md(f"The deepest CPT reading is at {_deepest_cpt:+.1f} m NAP.")]),
        ],
        widths=[3, 1],
        gap=2,
    )
    return base_cut, min_metres, split_by_lithology, unit_domains


@app.cell
def samples(cpts, pl, voxels):
    # CPT readings averaged per voxel they pass through: the column from x and y (its south-west corner),
    # the 0.5 m level from the nearest voxel centre
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
            pl.when(_unit_domain == "all units")
            .then(_lith_group)
            .otherwise(pl.concat_str([_unit_domain, _lith_group], separator=" · "))
        )
    else:
        _domain = _unit_domain
    DOMAIN = pl.when((_unit_domain != "not simulated") & (pl.col("z") >= base_cut.value)).then(_domain).alias("domain")

    voxel_domains = voxels.with_columns(DOMAIN)
    sample_domains = samples.with_columns(DOMAIN).drop_nulls("domain")

    # The domains from the top down, in GeoTOP's colour where a domain is one unit or one lithology group
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
    min_metres,
    pl,
    sample_domains,
    voxel_domains,
):
    _per_cpt = sample_domains.group_by("domain", "bro_id").agg((pl.len() * 0.5).alias("metres"))
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
                (pl.col("metres") >= min_metres.value).sum().alias("CPTs"),
                pl.sum("metres").alias("CPT metres"),
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
        .with_columns(pl.col("CPTs", "CPT metres").fill_null(0))
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
def domain_table(domain_summary, min_metres, mo, voxel_domains):
    _not_simulated = voxel_domains["domain"].null_count()
    mo.vstack(
        [
            mo.md(
                f"## 1 · {domain_summary.height} domains\n\n"
                f"{100 * _not_simulated / voxel_domains.height:.1f} % of the voxels are not simulated. "
                f"A domain needs about 20 CPTs for a horizontal and a vertical variogram, and 5 for a vertical one; "
                f"a CPT counts for a domain with at least {min_metres.value} m in it."
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
def coverage(alt, domain_scale, domain_summary, min_metres, pl):
    # How much of the model each domain fills, and how many CPTs condition it
    _order = domain_summary["domain"].to_list()
    _base = alt.Chart(domain_summary).encode(
        y=alt.Y("domain:N", sort=_order, title=None),
        color=alt.Color("domain:N", scale=domain_scale, legend=None),
        tooltip=["domain", "voxels", "% of model", "CPTs", "CPT metres", "variogram"],
    )
    _share = _base.mark_bar().encode(x=alt.X("% of model:Q", title="Share of the model (%)")).properties(width=260)
    # The CPTs a domain needs for a vertical variogram (5) and for a horizontal one too (20), labelled
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
        _base.mark_bar().encode(x=alt.X("CPTs:Q", title=f"CPTs with at least {min_metres.value} m in the domain")),
        _rules,
        *_labels,
    ).properties(width=320)
    alt.hconcat(_share, _cpts).resolve_scale(y="shared")
    return


@app.cell(hide_code=True)
def viewer_intro(mo):
    mo.md(r"""
    ## 2 · The domains in 3D

    The simulated voxels in their domain's colour, and the CPTs as dark sticks from their top to their
    base, among the buildings of PDOK's 3D BAG. Click a voxel or a CPT to see it below.
    """)
    return


@app.cell
def domain_bimdf(DOMAIN_COLORS, bpl, cpts, geotop_bimdf, pl, voxel_domains):
    def _rgba(hex_color):
        return [int(hex_color[_i : _i + 2], 16) / 255 for _i in (1, 3, 5)] + [1.0]


    # The simulated voxels, each box in its domain's colour, with its domain as its class
    _voxels = (
        geotop_bimdf.with_columns(voxel_domains["domain"])
        .filter(pl.col("domain").is_not_null())
        .with_columns(
            pl.col("domain").cast(pl.Categorical).alias("class"),
            mesh=pl.struct(
                vertices=pl.col("mesh").struct.field("vertices"),
                faces=pl.col("mesh").struct.field("faces"),
                styles=pl.concat_list(
                    pl.struct(
                        name=pl.col("domain"),
                        rgba=pl.col("domain").replace_strict(
                            {_d: _rgba(_c) for _d, _c in DOMAIN_COLORS.items()}, return_dtype=pl.List(pl.Float64)
                        ).list.to_array(4),
                        face_count=pl.lit(12, dtype=pl.UInt32),
                    )
                ),
            ).cast(bpl.MESH_DTYPE),
        )
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
    _cpt_sticks = bpl.to_crs(
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
    domain_bimdf = bpl.concat([_voxels, _cpt_sticks], how="diagonal_relaxed")
    return (domain_bimdf,)


@app.cell(hide_code=True)
def domain_viewer(GeoSpeckleViewer, domain_bimdf, mo, pdok_3d_buildings):
    domain_viewer = mo.ui.anywidget(
        GeoSpeckleViewer(domain_bimdf, tilesets=[pdok_3d_buildings(domain_bimdf)], height=550)
    )
    domain_viewer
    return (domain_viewer,)


@app.cell(hide_code=True)
def viewer_selection(domain_bimdf, domain_viewer, pl):
    # The voxels and CPTs selected in the GeoSpeckleViewer
    domain_bimdf.filter(
        pl.col("id").is_in([_obj["applicationId"] for _obj in domain_viewer.value["selected"]])
    ).select("id", "class", "name", "domain")
    return


@app.cell(hide_code=True)
def section_intro(mo):
    mo.md(r"""
    ## 3 · A cross-section

    One row of GeoTOP columns, coloured by domain, with the qc of the CPTs in that row drawn from their
    position (1 MPa per 2 m). Hover over a voxel or a trace for its values.
    """)
    return


@app.cell(hide_code=True)
def section_direction(mo):
    section_direction = mo.ui.radio(
        options={"West–east": "x", "South–north": "y"}, value="West–east", label="Section", inline=True
    )
    section_direction
    return (section_direction,)


@app.cell(hide_code=True)
def section_position(mo, pl, section_direction, voxels):
    # The section runs along one row (west–east) or column (south–north) of GeoTOP columns
    _across = "y" if section_direction.value == "x" else "x"
    _positions = voxels[_across].unique().sort().cast(pl.Int64).to_list()
    section_position = mo.ui.dropdown(
        options={f"{_p} – {_p + 100}": _p for _p in _positions},
        value=f"{_positions[len(_positions) // 2]} – {_positions[len(_positions) // 2] + 100}",
        label=f"through the columns at {_across} (RD, m)",
    )
    section_position
    return (section_position,)


@app.cell(hide_code=True)
def section(
    DOMAIN_COLORS,
    alt,
    pl,
    samples,
    section_direction,
    section_position,
    voxel_domains,
):
    _along = section_direction.value
    _across = "y" if _along == "x" else "x"
    _section = voxel_domains.filter(pl.col(_across) == section_position.value).with_columns(
        pl.col("domain").fill_null("not simulated"),
        along0=pl.col(_along),
        along1=pl.col(_along) + 100,
        z0=pl.col("z") - 0.25,
        z1=pl.col("z") + 0.25,
    )
    _scale = alt.Scale(domain=[*DOMAIN_COLORS, "not simulated"], range=[*DOMAIN_COLORS.values(), "#e8e8e8"])
    _voxels = (
        alt.Chart(_section)
        .mark_rect()
        .encode(
            x=alt.X("along0:Q", title=f"{_along} (RD, m)", scale=alt.Scale(zero=False, nice=False)),
            x2="along1:Q",
            y=alt.Y("z0:Q", title="z (m NAP)"),
            y2="z1:Q",
            color=alt.Color("domain:N", scale=_scale, title="Domain"),
            tooltip=["domain", "stratigraphic_unit", "grondsoort", "z", "x", "y"],
        )
    )
    # The CPTs in this row of columns: their qc drawn from their position along the section
    _traces = samples.filter(pl.col(f"column_{_across}") == section_position.value).with_columns(
        trace=pl.col(_along) + 2 * pl.col("qc")
    )
    _lines = (
        alt.Chart(_traces)
        .mark_line(color="black", strokeWidth=1)
        .encode(x="trace:Q", y="z:Q", detail="bro_id:N", order="z:Q", tooltip=["bro_id", "z", "qc", "rf"])
    )
    _positions = (
        alt.Chart(_traces.group_by("bro_id").agg(pl.first(_along)))
        .mark_rule(color="black", opacity=0.3)
        .encode(x=f"{_along}:Q")
    )
    (_voxels + _positions + _lines).properties(
        width="container", height=420, title=f"{_traces['bro_id'].n_unique()} CPTs in this row of columns"
    )
    return


@app.cell(hide_code=True)
def separation_intro(mo):
    mo.md(r"""
    ## 4 · Do the domains separate the CPT data?

    The 0.5 m CPT samples per domain, from the softest to the stiffest. Domains are useful when their
    boxes differ from their neighbours' and are narrow inside. Click a domain in the legend of the qc–Rf
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


if __name__ == "__main__":
    app.run()
