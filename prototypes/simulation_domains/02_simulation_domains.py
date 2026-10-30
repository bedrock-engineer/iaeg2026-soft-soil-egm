# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "bromodels==0.0.1",
#     "marimo",
#     "matplotlib",
#     "netcdf4",
#     "numpy",
#     "pandas",
#     "polars",
#     "pyarrow",
#     "xarray",
# ]
# ///

# PROTOTYPE: throwaway notebook for the ticket
# "Which geological units does the model distinguish?" (issue #5).

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 02 · Simulation domains: what are the options?  *(prototype)*

    A **geological unit** is a GeoTOP stratigraphic unit. A **simulation domain** is a group of voxels that share one variogram and one set of conditioning CPT data. This notebook compares ways of grouping GeoTOP voxels into simulation domains, using the CPTs in the model extent. Pick a scheme and compare:

    1. the summary table: does each domain have enough CPTs for a variogram?
    2. the cross-section: what do the domains look like?
    3. the qc / Rf distributions: do the domains actually separate the CPT data?

    Run `01_get_data.py` first to fill `data/`.
    """)
    return


@app.cell
def _():
    from pathlib import Path

    import bromodels
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import polars as pl
    import xarray as xr
    from matplotlib.colors import ListedColormap
    return ListedColormap, Path, bromodels, mo, np, pl, plt, xr


@app.cell
def _(Path, bromodels, mo, pl, xr):
    DATA_DIR = Path(mo.notebook_dir()) / "data"
    geotop = xr.open_dataset(DATA_DIR / "geotop.nc").load()
    cpts_raw = pl.read_parquet(DATA_DIR / "cpts.parquet")

    _strat = pl.from_pandas(bromodels.GTM.GeoTop.geotop_stratigraphic_unit()).unique("VOXEL_NR", keep="first")
    _lith = pl.from_pandas(bromodels.GTM.GeoTop.geotop_lithology_class()).drop_nulls("VOXEL_NR")


    def _hex(df):
        return df.select(
            pl.format("#{}{}{}", *[pl.col(c).cast(pl.Int64).map_elements(lambda v: f"{v:02x}", return_dtype=pl.String) for c in ("RED_DEC", "GREEN_DEC", "BLUE_DEC")])
        ).to_series()


    STRAT = dict(zip(_strat["VOXEL_NR"].cast(pl.Int64), _strat["STR_UNIT_CD"]))
    STRAT_DESC = dict(zip(_strat["STR_UNIT_CD"], _strat["DESCRIPTION"]))
    STRAT_COLOR = dict(zip(_strat["STR_UNIT_CD"], _hex(_strat)))
    LITH = dict(zip(_lith["VOXEL_NR"].cast(pl.Int64), _lith["LITHO_CLASS_CD"]))
    return DATA_DIR, LITH, STRAT, STRAT_COLOR, STRAT_DESC, cpts_raw, geotop


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Choices
    """)
    return


@app.cell
def _(mo):
    SCHEMES = {
        "A · every GeoTOP unit": "Each stratigraphic unit is its own domain.",
        "B · main units, thin units pooled": "ANAWA→NAWA, NAWOVE→NAWO, BX→BXWISIKO, NIBA→NIHO. Anthropogenic fill (AAOP) is not simulated.",
        "C · B, Eem cut at the CPT base": "As B, but voxels below the cut depth are not simulated (no CPT reaches them).",
        "D · unit × lithology": "B's units split by GeoTOP lithology group (peat / clay / clayey sand / sand).",
        "E · lithology only": "Ignore units; domains are GeoTOP lithology groups (a 'geotechnical' grouping).",
    }
    scheme = mo.ui.dropdown(options=list(SCHEMES), value="B · main units, thin units pooled", label="Domain scheme")
    z_cut = mo.ui.number(start=-50, stop=-20, step=0.5, value=-35, label="Cut depth for scheme C (m NAP)")
    xy_convention = mo.ui.radio(
        options={"x/y as returned by bromodels": 0.0, "x/y are cell corners (+50 m, per nlmod)": 50.0},
        value="x/y as returned by bromodels",
        label="GeoTOP x/y convention",
    )
    min_metres = mo.ui.number(start=0.5, stop=5, step=0.5, value=1.0, label="A CPT counts for a domain with at least (m)")
    return SCHEMES, min_metres, scheme, xy_convention, z_cut


@app.cell
def _(SCHEMES, min_metres, mo, scheme, xy_convention, z_cut):
    mo.vstack([mo.hstack([scheme, z_cut, min_metres], justify="start"), xy_convention, mo.md(f"*{SCHEMES[scheme.value]}*")])
    return


@app.cell
def _(LITH, STRAT, geotop, np, pl, xy_convention):
    # GeoTOP voxels as a table with cell centres.
    _df = geotop[["strat", "lithok"]].to_dataframe().reset_index()
    _shift = xy_convention.value
    voxels = (
        pl.from_pandas(_df)
        .drop_nulls(["strat"])
        .filter(pl.col("strat").is_not_nan())
        .with_columns(
            (pl.col("x") + _shift).alias("x"),
            (pl.col("y") + _shift).alias("y"),
            pl.col("strat").cast(pl.Int64).replace_strict(STRAT, default="?").alias("unit"),
            pl.col("lithok").fill_nan(None).cast(pl.Int64).replace_strict(LITH, default="o").alias("lith"),
        )
    )
    DX = float(np.diff(np.unique(voxels["x"])).min())
    DY = float(np.diff(np.unique(voxels["y"])).min())
    DZ = float(np.diff(np.unique(voxels["z"])).min())
    return DX, DY, DZ, voxels


@app.cell
def _(DX, DY, DZ, cpts_raw, pl, voxels):
    # Average CPT readings onto the GeoTOP 0.5 m z-levels and attach the voxel each sample sits in.
    _xs = voxels["x"].unique().sort()
    _ys = voxels["y"].unique().sort()
    _zs = voxels["z"].unique().sort()
    _x0, _y0, _z0 = _xs.min() - DX / 2, _ys.min() - DY / 2, _zs.min() - DZ / 2

    samples = (
        cpts_raw.with_columns(
            (_x0 + DX / 2 + ((pl.col("x") - _x0) / DX).floor() * DX).alias("vx"),
            (_y0 + DY / 2 + ((pl.col("y") - _y0) / DY).floor() * DY).alias("vy"),
            (_z0 + DZ / 2 + ((pl.col("z") - _z0) / DZ).floor() * DZ).round(3).alias("vz"),
        )
        .group_by("bro_id", "vx", "vy", "vz")
        .agg(
            pl.first("x", "y"),
            pl.col("qc").median(),
            pl.col("fs").median(),
            pl.col("rf").median(),
            pl.len().alias("n_readings"),
        )
        .join(
            voxels.select(pl.col("x").alias("vx"), pl.col("y").alias("vy"), pl.col("z").round(3).alias("vz"), "unit", "lith"),
            on=["vx", "vy", "vz"],
            how="left",
        )
    )
    _all = samples["bro_id"].n_unique()
    samples = samples.drop_nulls("unit")
    n_outside = _all - samples["bro_id"].n_unique()
    return n_outside, samples


@app.cell
def _(pl, scheme, z_cut):
    LITH_GROUP = {"v": "peat", "k": "clay", "kz": "clayey sand", "z": "sand", "zf": "sand", "zm": "sand", "zg": "sand", "g": "sand", "she": "sand", "a": "fill", "o": "other"}
    POOL = {"ANAWA": "NAWA", "NAWOVE": "NAWO", "BX": "BXWISIKO", "NIBA": "NIHO"}


    def domain_expr(name: str) -> pl.Expr:
        """Domain per row of a frame with columns unit, lith, z. Null = not simulated."""
        unit = pl.col("unit")
        pooled = unit.replace(POOL)
        lith_group = pl.col("lith").replace_strict(LITH_GROUP, default="other")
        not_fill = unit != "AAOP"
        if name.startswith("A"):
            return unit
        if name.startswith("B"):
            return pl.when(not_fill).then(pooled)
        if name.startswith("C"):
            return pl.when(not_fill & (pl.col("z") >= z_cut.value)).then(pooled)
        if name.startswith("D"):
            return pl.when(not_fill).then(pl.concat_str([pooled, lith_group], separator=" · "))
        if name.startswith("E"):
            return pl.when(not_fill).then(lith_group)
        raise ValueError(name)


    DOMAIN = domain_expr(scheme.value).alias("domain")
    return (DOMAIN,)


@app.cell
def _(DOMAIN, DZ, min_metres, pl, samples, voxels):
    vox_d = voxels.with_columns(DOMAIN)
    smp_d = samples.with_columns(pl.col("vz").alias("z")).with_columns(DOMAIN).drop_nulls("domain")

    _per_cpt = smp_d.group_by("domain", "bro_id").agg((pl.len() * DZ).alias("metres"))
    _cpt_stats = _per_cpt.group_by("domain").agg(
        (pl.col("metres") >= min_metres.value).sum().alias("CPTs ≥ min"),
        pl.col("metres").sum().alias("CPT metres"),
    )
    _vals = smp_d.group_by("domain").agg(
        pl.len().alias("0.5 m samples"),
        pl.col("qc").median().round(2).alias("median qc (MPa)"),
        (pl.col("qc").log10().quantile(0.75) - pl.col("qc").log10().quantile(0.25)).round(2).alias("IQR log10 qc"),
        pl.col("rf").median().round(2).alias("median Rf (%)"),
    )
    _n_vox = vox_d.height
    summary = (
        vox_d.group_by("domain")
        .agg(pl.len().alias("voxels"))
        .with_columns((100 * pl.col("voxels") / _n_vox).round(1).alias("% of model"))
        .join(_cpt_stats, on="domain", how="left")
        .join(_vals, on="domain", how="left")
        .with_columns(pl.col("CPTs ≥ min", "CPT metres", "0.5 m samples").fill_null(0))
        .with_columns(
            pl.when(pl.col("domain").is_null())
            .then(pl.lit("not simulated"))
            .when(pl.col("CPTs ≥ min") >= 20)
            .then(pl.lit("✅ variogram OK"))
            .when(pl.col("CPTs ≥ min") >= 5)
            .then(pl.lit("⚠️ marginal"))
            .otherwise(pl.lit("❌ too few CPTs"))
            .alias("verdict")
        )
        .sort("voxels", descending=True)
    )
    return smp_d, summary, vox_d


@app.cell(hide_code=True)
def _(mo, n_outside, samples, scheme, summary):
    mo.vstack(
        [
            mo.md(f"## 1 · Domains in scheme {scheme.value}"),
            mo.md(
                f"{samples['bro_id'].n_unique()} CPTs fall inside GeoTOP voxels ({n_outside} more lie in the extent but outside the GeoTOP columns). "
                "Verdict rule of thumb: ≥ 20 CPTs → horizontal + vertical variogram; 5–19 → vertical only or borrow a variogram; < 5 → pool or skip."
            ),
            mo.ui.table(summary, selection=None, page_size=40),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2 · Cross-section
    """)
    return


@app.cell
def _(mo, voxels):
    _xs = voxels["x"].unique().sort().to_list()
    _ys = voxels["y"].unique().sort().to_list()
    direction = mo.ui.radio(options=["W–E (fixed y)", "S–N (fixed x)"], value="W–E (fixed y)", label="Section")
    y_pick = mo.ui.dropdown(options={f"{v:.0f}": v for v in _ys}, value=f"{_ys[len(_ys) // 2]:.0f}", label="y (RD)")
    x_pick = mo.ui.dropdown(options={f"{v:.0f}": v for v in _xs}, value=f"{_xs[len(_xs) // 2]:.0f}", label="x (RD)")
    mo.hstack([direction, y_pick, x_pick], justify="start")
    return direction, x_pick, y_pick


@app.cell
def _(
    DX,
    DY,
    DZ,
    ListedColormap,
    STRAT_COLOR,
    direction,
    np,
    pl,
    plt,
    smp_d,
    vox_d,
    x_pick,
    y_pick,
):
    _we = direction.value.startswith("W")
    _along, _fixed, _fixed_val, _half = ("x", "y", y_pick.value, DY / 2) if _we else ("y", "x", x_pick.value, DX / 2)
    _sec = vox_d.filter(pl.col(_fixed) == _fixed_val)

    _domains = vox_d["domain"].drop_nulls().unique().sort().to_list()
    _code = {d: i for i, d in enumerate(_domains)}
    _tab = plt.get_cmap("tab20")
    _colors = [STRAT_COLOR.get(d, _tab(i % 20)) for i, d in enumerate(_domains)]
    _cmap = ListedColormap(_colors if _colors else ["#ccc"])

    _a = np.sort(_sec[_along].unique().to_numpy())
    _z = np.sort(_sec["z"].unique().to_numpy())
    _grid = np.full((len(_z), len(_a)), np.nan)
    _ai = {v: i for i, v in enumerate(_a)}
    _zi = {v: i for i, v in enumerate(_z)}
    for _r in _sec.iter_rows(named=True):
        if _r["domain"] is not None:
            _grid[_zi[_r["z"]], _ai[_r[_along]]] = _code[_r["domain"]]

    _fig, _ax = plt.subplots(figsize=(13, 6))
    _ax.imshow(
        _grid,
        origin="lower",
        aspect="auto",
        cmap=_cmap,
        vmin=-0.5,
        vmax=len(_domains) - 0.5,
        extent=[_a.min() - (DX if _we else DY) / 2, _a.max() + (DX if _we else DY) / 2, _z.min() - DZ / 2, _z.max() + DZ / 2],
        interpolation="nearest",
    )
    # CPTs within half a column of the section, drawn as qc traces (1 MPa ≈ 2 m on the section axis).
    _near = smp_d.filter((pl.col(_fixed) - _fixed_val).abs() <= _half)
    for _cpt in _near.partition_by("bro_id"):
        _cpt = _cpt.sort("vz")
        _pos = _cpt[_along][0]
        _ax.axvline(_pos, color="k", lw=0.5, alpha=0.4)
        _ax.plot(_pos + 2 * _cpt["qc"].to_numpy(), _cpt["vz"].to_numpy(), color="k", lw=0.8)
    for _d, _c in zip(_domains, _colors):
        _ax.plot([], [], "s", color=_c, label=_d)
    _ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8, frameon=False)
    _ax.set_xlabel(f"{_along} (RD, m)")
    _ax.set_ylabel("z (m NAP)")
    _ax.set_title(f"{direction.value} at {_fixed} = {_fixed_val:.0f}; white = not simulated; black = qc of {_near['bro_id'].n_unique()} CPTs within ±{_half:.0f} m")
    _fig.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3 · Do the domains separate the CPT data?

    Each box shows the 0.5 m-averaged CPT samples in one domain. Domains are useful when their boxes differ from their neighbours' and are narrow inside.
    """)
    return


@app.cell
def _(np, pl, plt, smp_d, summary):
    _order = summary.drop_nulls("domain").filter(pl.col("0.5 m samples") > 0).sort("median qc (MPa)")["domain"].to_list()
    _qc = [np.log10(smp_d.filter(pl.col("domain") == d)["qc"].to_numpy()) for d in _order]
    _rf = [smp_d.filter(pl.col("domain") == d)["rf"].drop_nulls().clip(0, 15).to_numpy() for d in _order]
    _fig, (_a1, _a2) = plt.subplots(1, 2, figsize=(13, 0.35 * len(_order) + 1.5))
    _a1.boxplot(_qc, orientation="horizontal", tick_labels=_order, showfliers=False)
    _a1.set_xlabel("log10 qc (MPa)")
    _a2.boxplot(_rf, orientation="horizontal", tick_labels=[""] * len(_order), showfliers=False)
    _a2.set_xlabel("Rf (%)")
    _fig.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4 · Where are the CPTs?
    """)
    return


@app.cell
def _(DX, DY, pl, plt, smp_d, voxels):
    _fig, _ax = plt.subplots(figsize=(6, 6))
    for _x in voxels["x"].unique():
        for _y in voxels["y"].unique():
            _ax.add_patch(plt.Rectangle((_x - DX / 2, _y - DY / 2), DX, DY, fill=False, lw=0.5, color="grey"))
    _pts = smp_d.group_by("bro_id").agg(pl.first("x", "y"), pl.col("vz").min().alias("base"))
    _sc = _ax.scatter(_pts["x"], _pts["y"], c=_pts["base"], cmap="viridis", s=18)
    _fig.colorbar(_sc, label="CPT base (m NAP)")
    _ax.set_aspect("equal")
    _ax.set_title("GeoTOP columns (grey) and CPTs")
    _ax.autoscale()
    _fig
    return


if __name__ == "__main__":
    app.run()
