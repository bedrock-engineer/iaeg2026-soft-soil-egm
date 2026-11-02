# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair",
#     "gstools==1.7.0",
#     "marimo>=0.25.2",
#     "marimo-lens==0.2.4",
#     "numpy",
#     "polars==2.1.0",
#     "pyarrow",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Variograms

    A variogram per simulation domain describes how fast a CPT parameter loses its correlation with
    distance: vertically along a CPT, and horizontally between CPTs at one level. `04` uses them to
    simulate the parameter in each domain's voxels.

    Reads the simulation domains that `02_simulation_domains.py` saves: their definition in
    `notebooks/simulation_domains.json` and the 0.5 m CPT samples with their domain in
    `data/sample_domains.parquet`. The variograms are of **normal scores**: per domain, the parameter
    (log₁₀ of qc and fs), optionally without its linear trend with depth, ranked and mapped onto a
    standard normal distribution. Their sill is therefore 1.
    """)
    return


@app.cell
def _():
    import json
    from datetime import datetime
    from pathlib import Path
    from statistics import NormalDist

    import altair as alt
    import gstools as gs
    import marimo as mo
    import numpy as np
    import polars as pl
    from marimo_lens import Lens

    # The charts take thousands of CPT sample pairs
    alt.data_transformers.disable_max_rows()
    return Lens, NormalDist, Path, alt, datetime, gs, json, mo, np, pl


@app.cell(hide_code=True)
def _(Lens):
    # marimo-lens: select a region of any output and add a note for the notebook agent
    lens = Lens()
    lens
    return


@app.cell
def inputs(Path, mo):
    DATA_DIR = Path(mo.notebook_dir()).parent / "data"
    # The simulation domains 02_simulation_domains.py saves, and the variograms this notebook saves for 04.
    # The cells that read them run again when they are saved.
    DOMAINS_JSON = Path(mo.notebook_dir()) / "simulation_domains.json"
    VARIOGRAMS_JSON = Path(mo.notebook_dir()) / "variograms.json"
    domains_json = mo.watch.file(DOMAINS_JSON)
    samples_parquet = mo.watch.file(DATA_DIR / "sample_domains.parquet")
    variograms_json = mo.watch.file(VARIOGRAMS_JSON)
    return VARIOGRAMS_JSON, domains_json, samples_parquet, variograms_json


@app.cell
def read_inputs(Path, domains_json, json, mo, pl, samples_parquet):
    mo.stop(
        not (Path(domains_json).exists() and Path(samples_parquet).exists()),
        mo.md("Save the simulation domains in `02_simulation_domains.py` first."),
    )
    domain_definition = json.loads(Path(domains_json).read_text(encoding="utf-8"))
    # The domains from the top down, in the colours 02 gave them
    DOMAIN_COLORS = domain_definition["colors"]
    samples = pl.read_parquet(Path(samples_parquet))
    mo.md(
        f"**{samples.height} CPT samples** of 0.5 m from {samples['bro_id'].n_unique()} CPTs in "
        f"**{len(DOMAIN_COLORS)} simulation domains**, saved in `02` on {domain_definition['saved']}."
    )
    return DOMAIN_COLORS, domain_definition, samples


@app.cell(hide_code=True)
def data_intro(mo):
    mo.md(r"""
    ## 1 · The data per domain

    Choose the parameter and the variogram model. With the trend removed, each domain's linear trend with
    depth comes off before the normal-score transform, so the variograms describe what varies around it;
    `04` adds the trend back.
    """)
    return


@app.cell(hide_code=True)
def parameter(gs, mo):
    # The CPT parameters, each with how it is transformed before its normal scores
    PARAMETERS = {"qc (cone resistance)": "qc", "fs (sleeve friction)": "fs", "Rf (friction ratio)": "rf"}
    LOG_PARAMETERS = {"qc", "fs"}
    # GSTools' covariance models; a model's len_scale is what 04 passes on
    MODELS = {"Exponential": gs.Exponential, "Spherical": gs.Spherical, "Gaussian": gs.Gaussian}
    parameter = mo.ui.dropdown(PARAMETERS, value="qc (cone resistance)", label="Parameter")
    model = mo.ui.dropdown(list(MODELS), value="Exponential", label="Variogram model")
    detrend = mo.ui.switch(value=True, label="Remove each domain's linear trend with depth")
    mo.hstack([parameter, model, detrend], justify="start", gap=2)
    return LOG_PARAMETERS, MODELS, PARAMETERS, detrend, model, parameter


@app.cell
def scores(LOG_PARAMETERS, NormalDist, detrend, parameter, pl, samples):
    # Per domain: the parameter (log10 of qc and fs), its linear trend with depth (none with detrend off),
    # and the normal scores of what is left around it: ranked and mapped onto a standard normal distribution
    _value = pl.col(parameter.value).log10() if parameter.value in LOG_PARAMETERS else pl.col(parameter.value)
    _data = samples.filter(pl.col(parameter.value) > 0).with_columns(value=_value)
    trends = (
        _data.group_by("domain")
        .agg(
            samples=pl.len(),
            cpts=pl.n_unique("bro_id"),
            mean=pl.mean("value"),
            std=pl.col("value").std(),
            slope=(pl.cov("z", "value") / pl.col("z").var()).fill_nan(0.0) if detrend.value else pl.lit(0.0),
            mean_z=pl.mean("z"),
        )
        .with_columns(intercept=pl.col("mean") - pl.col("slope") * pl.col("mean_z"))
        .drop("mean_z")
    )
    _inverse_normal = NormalDist().inv_cdf
    scores = (
        _data.join(trends.select("domain", "slope", "intercept"), on="domain")
        .with_columns(residual=pl.col("value") - (pl.col("intercept") + pl.col("slope") * pl.col("z")))
        .with_columns(
            score=((pl.col("residual").rank("average").over("domain") - 0.5) / pl.len().over("domain")).map_elements(
                _inverse_normal, return_dtype=pl.Float64
            )
        )
        .select("domain", "bro_id", "x", "y", "z", "value", "residual", "score")
    )
    return scores, trends


@app.cell(hide_code=True)
def data_table(DOMAIN_COLORS, LOG_PARAMETERS, mo, parameter, pl, trends):
    # The domains from the top down, in their colours
    _unit = "log₁₀ MPa" if parameter.value in LOG_PARAMETERS else "%"
    mo.ui.table(
        pl.DataFrame({"domain": list(DOMAIN_COLORS)})
        .join(trends, on="domain", how="left", maintain_order="left")
        .select(
            "domain",
            pl.col("samples").alias("samples (0.5 m)"),
            pl.col("cpts").alias("CPTs"),
            pl.col("mean").round(3).alias(f"mean ({_unit})"),
            pl.col("std").round(3).alias(f"std ({_unit})"),
            (-pl.col("slope")).round(4).alias(f"change with depth ({_unit} per m)"),
        ),
        selection=None,
        style_cell=lambda _row, column, value: {"backgroundColor": DOMAIN_COLORS[value]} if column == "domain" else {},
    )
    return


@app.cell
def lags():
    # The experimental variograms: vertically up to MAX_LAG["vertical"] along each CPT, in steps of the
    # samples' 0.5 m; horizontally up to MAX_LAG["horizontal"] between CPTs at one level, in bins of
    # HORIZONTAL_BIN. A lag needs MIN_PAIRS pairs of samples to count in the fit.
    MAX_LAG = {"vertical": 10.0, "horizontal": 300.0}
    HORIZONTAL_BIN = 20.0
    MIN_PAIRS = 30
    # The length scales a fit and the sliders can take, in m
    LEN_SCALE_BOUNDS = {"vertical": [0.1, 10.0], "horizontal": [5.0, 1000.0]}
    return HORIZONTAL_BIN, LEN_SCALE_BOUNDS, MAX_LAG, MIN_PAIRS


@app.cell
def experimental(HORIZONTAL_BIN, MAX_LAG, pl, scores):
    # Half the mean squared difference between the normal scores of pairs of samples in one domain, per lag
    _s = scores.select("domain", "bro_id", "x", "y", "z", "score")
    _semivariance = 0.5 * ((pl.col("score") - pl.col("score_2")) ** 2).mean()
    # Vertically: pairs of samples of one CPT, the upper one first
    _vertical = (
        _s.join(_s, on=["domain", "bro_id"], suffix="_2")
        .with_columns(lag=pl.col("z") - pl.col("z_2"))
        .filter((pl.col("lag") > 0) & (pl.col("lag") <= MAX_LAG["vertical"]))
        .group_by("domain", "lag")
        .agg(gamma=_semivariance, pairs=pl.len())
        .with_columns(direction=pl.lit("vertical"))
    )
    # Horizontally: pairs of samples of two CPTs at one level, each pair once, at their mean distance per bin
    _horizontal = (
        _s.join(_s, on=["domain", "z"], suffix="_2")
        .filter(pl.col("bro_id") < pl.col("bro_id_2"))
        .with_columns(distance=((pl.col("x") - pl.col("x_2")) ** 2 + (pl.col("y") - pl.col("y_2")) ** 2).sqrt())
        .filter(pl.col("distance") <= MAX_LAG["horizontal"])
        .group_by("domain", (pl.col("distance") // HORIZONTAL_BIN).alias("bin"))
        .agg(lag=pl.mean("distance"), gamma=_semivariance, pairs=pl.len())
        .drop("bin")
        .with_columns(direction=pl.lit("horizontal"))
    )
    experimental = pl.concat([_vertical, _horizontal], how="diagonal").sort("domain", "direction", "lag")
    return (experimental,)


@app.cell
def fit(
    DOMAIN_COLORS,
    LEN_SCALE_BOUNDS,
    MIN_PAIRS,
    MODELS,
    experimental,
    model,
    pl,
):
    def _fit(points, nugget, len_scale_bounds):
        """A model fitted by least squares to the points of one direction, with a sill of 1 and the lags
        weighted by their pairs: its nugget (fitted when nugget is True) and len_scale, within
        len_scale_bounds, or None with too few lags"""
        points = points.filter(pl.col("pairs") >= MIN_PAIRS)
        if points.height < 3:
            return None
        _model = MODELS[model.value](dim=1)
        _model.len_scale_bounds = len_scale_bounds
        try:
            _model.fit_variogram(
                points["lag"].to_numpy(),
                points["gamma"].to_numpy(),
                sill=1.0,
                nugget=nugget,
                weights=points["pairs"].to_numpy(),
                loss="linear",
            )
        except (RuntimeError, ValueError):
            return None
        return _model.nugget, _model.len_scale


    # Per domain, the model fitted to the experimental variograms: the nugget from the vertical one, which has
    # the short lags, and the horizontal one fitted with that nugget
    fitted = {}
    for _domain in DOMAIN_COLORS:
        _points = experimental.filter(pl.col("domain") == _domain)
        _vertical = _fit(_points.filter(pl.col("direction") == "vertical"), nugget=True, len_scale_bounds=LEN_SCALE_BOUNDS["vertical"])
        _nugget = _vertical[0] if _vertical else 0.0
        _horizontal = _fit(
            _points.filter(pl.col("direction") == "horizontal"), nugget=_nugget, len_scale_bounds=LEN_SCALE_BOUNDS["horizontal"]
        )
        fitted[_domain] = {
            "nugget": _nugget,
            "vertical": _vertical[1] if _vertical else None,
            "horizontal": _horizontal[1] if _horizontal else None,
        }
    fitted
    return (fitted,)


@app.cell
def saved_variograms(Path, json, variograms_json):
    # The variograms saved before, per parameter; empty until they are saved
    saved_variograms = json.loads(Path(variograms_json).read_text(encoding="utf-8")) if Path(variograms_json).exists() else {}
    return (saved_variograms,)


@app.cell(hide_code=True)
def variograms_intro(mo):
    reset_to_fit = mo.ui.run_button(label="Start again from the fit")
    mo.vstack(
        [
            mo.md(r"""
    ## 2 · The variograms per domain

    Each row is one domain: its sliders, its vertical variogram along the CPTs and its horizontal one
    between CPTs at one level. The dots are the experimental variogram, as
    large as their number of pairs of samples, and faint below the number a lag needs to count in the fit.
    The line is the model of the sliders, which start from the saved variograms when they are of this
    parameter, model and trend, and otherwise from a weighted least-squares fit with a sill of 1. Both
    directions share the nugget.
    """),
            reset_to_fit,
        ]
    )
    return (reset_to_fit,)


@app.cell(hide_code=True)
def variogram_controls(
    DOMAIN_COLORS,
    LEN_SCALE_BOUNDS,
    detrend,
    fitted,
    mo,
    model,
    parameter,
    reset_to_fit,
    saved_variograms,
):
    # Where a domain's sliders start: its saved variogram, when the saved variograms are of this parameter,
    # model and trend; otherwise its fit, or DEFAULTS where there is none
    DEFAULTS = {"nugget": 0.0, "vertical": 1.0, "horizontal": 100.0}
    _saved = saved_variograms.get(parameter.value, {})
    _use_saved = not reset_to_fit.value and _saved.get("model") == model.value and _saved.get("detrend") == detrend.value


    def _start(domain, key):
        if _use_saved and domain in _saved["domains"]:
            _variogram = _saved["domains"][domain]
            return _variogram["nugget"] if key == "nugget" else _variogram["len_scale"][key]
        _value = fitted[domain][key]
        return DEFAULTS[key] if _value is None else float(_value)


    def _slider(bounds, step, value, label):
        _value = round(round(min(max(value, bounds[0]), bounds[1]) / step) * step, 2)
        return mo.ui.slider(start=bounds[0], stop=bounds[1], step=step, value=_value, show_value=True, label=label)


    variogram_controls = mo.ui.dictionary(
        {
            _domain: mo.ui.dictionary(
                {
                    "nugget": _slider([0.0, 1.0], 0.01, _start(_domain, "nugget"), "Nugget"),
                    "vertical": _slider(LEN_SCALE_BOUNDS["vertical"], 0.05, _start(_domain, "vertical"), "Vertical length scale (m)"),
                    "horizontal": _slider(LEN_SCALE_BOUNDS["horizontal"], 5.0, _start(_domain, "horizontal"), "Horizontal length scale (m)"),
                }
            )
            for _domain in DOMAIN_COLORS
        }
    )
    return (variogram_controls,)


@app.cell(hide_code=True, expand_output=True)
def variogram_rows(
    DOMAIN_COLORS,
    MAX_LAG,
    MIN_PAIRS,
    MODELS,
    alt,
    experimental,
    mo,
    model,
    np,
    pl,
    trends,
    variogram_controls,
):
    def model_of(controls, direction):
        """The GSTools model of a domain's sliders in one direction"""
        return MODELS[model.value](
            dim=1, var=1.0 - controls["nugget"], len_scale=controls[direction], nugget=controls["nugget"]
        )


    def _chart(domain, direction):
        _controls = variogram_controls.value[domain]
        _lags = np.linspace(0, MAX_LAG[direction], 200)[1:]
        _curve = pl.DataFrame({"lag": _lags, "gamma": model_of(_controls, direction).variogram(_lags)})
        _x = alt.X("lag:Q", title="Lag (m)", scale=alt.Scale(domain=[0, MAX_LAG[direction]]))
        _y = alt.Y("gamma:Q", title="Semivariance", scale=alt.Scale(domain=[0, 2], clamp=True))
        _points = (
            alt.Chart(experimental.filter((pl.col("domain") == domain) & (pl.col("direction") == direction)))
            .mark_circle(color=DOMAIN_COLORS[domain], stroke="#333", strokeWidth=0.6)
            .encode(
                x=_x,
                y=_y,
                size=alt.Size("pairs:Q", legend=None, scale=alt.Scale(range=[10, 220])),
                opacity=alt.condition(f"datum.pairs >= {MIN_PAIRS}", alt.value(1.0), alt.value(0.3)),
                tooltip=[alt.Tooltip("lag:Q", format=".1f"), alt.Tooltip("gamma:Q", format=".3f"), "pairs:Q"],
            )
        )
        _line = alt.Chart(_curve).mark_line(color="#333").encode(x=_x, y=_y)
        _sill = alt.Chart(pl.DataFrame({"gamma": [1.0]})).mark_rule(strokeDash=[4, 3], color="#999").encode(y="gamma:Q")
        _title = "Vertical, along the CPTs" if direction == "vertical" else "Horizontal, between CPTs at one level"
        return (_sill + _points + _line).properties(width=300, height=180, title=_title)


    def _row(domain):
        _controls = variogram_controls[domain]
        _trend = trends.filter(pl.col("domain") == domain).row(0, named=True)
        _ranges = {_d: model_of(variogram_controls.value[domain], _d).percentile_scale(0.95) for _d in ("vertical", "horizontal")}
        _about = mo.md(
            f'<span style="display:inline-block;width:12px;height:12px;background:{DOMAIN_COLORS[domain]};'
            f'border:1px solid #999;margin-right:6px"></span>**{domain}**\n\n'
            f"{_trend['cpts']} CPTs, {_trend['samples']} samples. 95 % of the sill at "
            f"{_ranges['vertical']:.1f} m vertically and {_ranges['horizontal']:.0f} m horizontally."
        )
        return mo.vstack(
            [
                _about,
                mo.hstack([_controls["nugget"], _controls["vertical"], _controls["horizontal"]], justify="start", gap=2),
                mo.hstack([_chart(domain, "vertical"), _chart(domain, "horizontal")], justify="start", gap=2),
            ]
        )


    mo.vstack([_row(_domain) for _domain in DOMAIN_COLORS], gap=2)
    return (model_of,)


@app.cell(hide_code=True)
def variograms(DOMAIN_COLORS, mo, model, model_of, pl, variogram_controls):
    # The variograms of the sliders, per domain, in GSTools' terms: the nugget and the variance (the partial
    # sill) add up to 1; a len_scale per direction
    variograms = pl.DataFrame(
        [
            {
                "domain": _domain,
                "model": model.value,
                "nugget": _controls["nugget"],
                "variance": round(1.0 - _controls["nugget"], 2),
                "len_scale vertical (m)": _controls["vertical"],
                "len_scale horizontal (m)": _controls["horizontal"],
                "anisotropy (vertical / horizontal)": round(_controls["vertical"] / _controls["horizontal"], 4),
                "95 % range vertical (m)": round(model_of(_controls, "vertical").percentile_scale(0.95), 2),
                "95 % range horizontal (m)": round(model_of(_controls, "horizontal").percentile_scale(0.95), 1),
            }
            for _domain, _controls in variogram_controls.value.items()
        ]
    )
    mo.vstack(
        [
            mo.md("## 3 · The variograms"),
            mo.ui.table(
                variograms,
                selection=None,
                style_cell=lambda _row, column, value: {"backgroundColor": DOMAIN_COLORS[value]} if column == "domain" else {},
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def save_intro(mo):
    mo.md(r"""
    ## 4 · Save the variograms

    Saving pins the variograms of this parameter for `04`. It writes them to `notebooks/variograms.json`,
    which is committed with the notebooks and keeps the variograms of the other parameters, each with its
    transform, its trend per domain and the date of the simulation domains it is based on.
    """)
    return


@app.cell(hide_code=True)
def variogram_definition(
    LOG_PARAMETERS,
    detrend,
    mo,
    model,
    parameter,
    trends,
    variogram_controls,
):
    # The variograms of this parameter as variograms.json holds them
    _trends = {_row["domain"]: _row for _row in trends.iter_rows(named=True)}
    variogram_definition = {
        "transform": "log10" if parameter.value in LOG_PARAMETERS else "none",
        "detrend": detrend.value,
        "model": model.value,
        "domains": {
            _domain: {
                "nugget": _controls["nugget"],
                "len_scale": {"horizontal": _controls["horizontal"], "vertical": _controls["vertical"]},
                # The trend of the transformed parameter: intercept + slope * z, z in m NAP
                "trend": {"intercept": _trends[_domain]["intercept"], "slope": _trends[_domain]["slope"]},
            }
            for _domain, _controls in variogram_controls.value.items()
        },
    }
    save_variograms = mo.ui.run_button(label="Save these variograms")
    save_variograms
    return save_variograms, variogram_definition


@app.cell(hide_code=True)
def saved_status(
    domain_definition,
    json,
    mo,
    parameter,
    saved_variograms,
    variogram_definition,
):
    # Whether the saved variograms of this parameter are the ones above, and of the saved simulation domains
    _saved = saved_variograms.get(parameter.value)
    if _saved is None:
        _status = mo.callout(mo.md(f"No variograms of {parameter.value} are saved yet."), kind="warn")
    elif _saved != json.loads(json.dumps(variogram_definition)):
        _status = mo.callout(
            mo.md(f"The variograms above differ from the ones of {parameter.value} saved on {saved_variograms['saved']}."),
            kind="warn",
        )
    elif saved_variograms["simulation_domains_saved"] != domain_definition["saved"]:
        _status = mo.callout(
            mo.md("The variograms above are the saved ones, but the simulation domains were saved again since. Save them again."),
            kind="warn",
        )
    else:
        _status = mo.callout(
            mo.md(f"The variograms above are the ones of {parameter.value} saved on {saved_variograms['saved']}."), kind="success"
        )
    _status
    return


@app.cell(hide_code=True)
def save(
    PARAMETERS,
    VARIOGRAMS_JSON,
    datetime,
    domain_definition,
    json,
    mo,
    parameter,
    save_variograms,
    saved_variograms,
    variogram_definition,
):
    mo.stop(not save_variograms.value)
    VARIOGRAMS_JSON.write_text(
        json.dumps(
            {
                **{_key: _value for _key, _value in saved_variograms.items() if _key in PARAMETERS.values()},
                "saved": datetime.now().isoformat(timespec="seconds"),
                "simulation_domains_saved": domain_definition["saved"],
                parameter.value: variogram_definition,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return


if __name__ == "__main__":
    app.run()
