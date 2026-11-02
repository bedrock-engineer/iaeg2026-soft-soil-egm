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

    Choose the parameters. With the trend removed, each domain's linear trend with depth comes off before
    the normal-score transform, so the variograms describe what varies around it; `04` adds the trend back.
    """)
    return


@app.cell(hide_code=True)
def parameter(gs, mo):
    # The CPT parameters, each with how it is transformed before its normal scores
    PARAMETERS = {
        "qc (cone resistance)": "qc",
        "fs (sleeve friction)": "fs",
        "Rf (friction ratio)": "rf",
    }
    LOG_PARAMETERS = {"qc", "fs"}
    UNITS = {"qc": "log₁₀ MPa", "fs": "log₁₀ MPa", "rf": "%"}
    # GSTools' covariance models a domain's variogram can follow; a model's len_scale is what 04 passes on
    MODELS = {
        "Exponential": gs.Exponential,
        "Spherical": gs.Spherical,
        "Gaussian": gs.Gaussian,
    }
    parameters = mo.ui.multiselect(
        PARAMETERS, value=["qc (cone resistance)", "fs (sleeve friction)"], label="Parameters"
    )
    detrend = mo.ui.switch(
        value=True, label="Remove each domain's linear trend with depth"
    )
    mo.hstack([parameters, detrend], justify="start", gap=2)
    return LOG_PARAMETERS, MODELS, PARAMETERS, UNITS, detrend, parameters


@app.cell
def scores(LOG_PARAMETERS, NormalDist, detrend, mo, parameters, pl, samples):
    mo.stop(not parameters.value, mo.md("Choose at least one parameter."))


    def _transformed(name):
        """The samples of one parameter, with its transformed value: log10 of qc and fs"""
        _value = pl.col(name).log10() if name in LOG_PARAMETERS else pl.col(name)
        return samples.filter(pl.col(name) > 0).select(
            "domain", "bro_id", "x", "y", "z", value=_value, parameter=pl.lit(name)
        )


    # Per parameter and domain: the transformed parameter, its linear trend with depth (none with detrend
    # off), and the normal scores of what is left around it: ranked and mapped onto a standard normal
    # distribution
    _data = pl.concat([_transformed(_name) for _name in parameters.value])
    trends = (
        _data.group_by("parameter", "domain")
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
    _group = ["parameter", "domain"]
    scores = (
        _data.join(trends.select(*_group, "slope", "intercept"), on=_group)
        .with_columns(residual=pl.col("value") - (pl.col("intercept") + pl.col("slope") * pl.col("z")))
        .with_columns(
            score=((pl.col("residual").rank("average").over(_group) - 0.5) / pl.len().over(_group)).map_elements(
                _inverse_normal, return_dtype=pl.Float64
            )
        )
        .select(*_group, "bro_id", "x", "y", "z", "value", "residual", "score")
    )
    return scores, trends


@app.cell(hide_code=True)
def data_table(DOMAIN_COLORS, UNITS, mo, parameters, pl, trends):
    # The parameters in the order they were chosen, each with its domains from the top down, in their colours
    _order = {
        "parameter": {_name: _i for _i, _name in enumerate(parameters.value)},
        "domain": {_domain: _i for _i, _domain in enumerate(DOMAIN_COLORS)},
    }
    mo.ui.table(
        trends.sort(*(pl.col(_column).replace_strict(_rank) for _column, _rank in _order.items())).select(
            "parameter",
            "domain",
            pl.col("samples").alias("samples (0.5 m)"),
            pl.col("cpts").alias("CPTs"),
            pl.col("parameter").replace_strict(UNITS).alias("unit"),
            pl.col("mean").round(3),
            pl.col("std").round(3),
            (-pl.col("slope")).round(4).alias("change with depth (unit per m)"),
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
    # Half the mean squared difference between the normal scores of pairs of samples of one parameter in one
    # domain, per lag
    _s = scores.select("parameter", "domain", "bro_id", "x", "y", "z", "score")
    _semivariance = 0.5 * ((pl.col("score") - pl.col("score_2")) ** 2).mean()
    # Vertically: pairs of samples of one CPT, the upper one first
    _vertical = (
        _s.join(_s, on=["parameter", "domain", "bro_id"], suffix="_2")
        .with_columns(lag=pl.col("z") - pl.col("z_2"))
        .filter((pl.col("lag") > 0) & (pl.col("lag") <= MAX_LAG["vertical"]))
        .group_by("parameter", "domain", "lag")
        .agg(gamma=_semivariance, pairs=pl.len())
        .with_columns(direction=pl.lit("vertical"))
    )
    # Horizontally: pairs of samples of two CPTs at one level, each pair once, at their mean distance per bin
    _horizontal = (
        _s.join(_s, on=["parameter", "domain", "z"], suffix="_2")
        .filter(pl.col("bro_id") < pl.col("bro_id_2"))
        .with_columns(distance=((pl.col("x") - pl.col("x_2")) ** 2 + (pl.col("y") - pl.col("y_2")) ** 2).sqrt())
        .filter(pl.col("distance") <= MAX_LAG["horizontal"])
        .group_by("parameter", "domain", (pl.col("distance") // HORIZONTAL_BIN).alias("bin"))
        .agg(lag=pl.mean("distance"), gamma=_semivariance, pairs=pl.len())
        .drop("bin")
        .with_columns(direction=pl.lit("horizontal"))
    )
    experimental = pl.concat([_vertical, _horizontal], how="diagonal").sort("parameter", "domain", "direction", "lag")
    return (experimental,)


@app.cell
def fit(
    DOMAIN_COLORS,
    LEN_SCALE_BOUNDS,
    MIN_PAIRS,
    MODELS,
    experimental,
    np,
    parameters,
    pl,
):
    def _fit(model_name, points, nugget, len_scale_bounds):
        """A model fitted by least squares to the points of one direction, with a sill of 1 and the lags
        weighted by their pairs: its nugget (fitted when nugget is True), its len_scale within
        len_scale_bounds and its misfit, the weighted root mean square of its residuals; or None with too
        few lags"""
        points = points.filter(pl.col("pairs") >= MIN_PAIRS)
        if points.height < 3:
            return None
        _lags, _gamma, _pairs = (points[_column].to_numpy() for _column in ("lag", "gamma", "pairs"))
        _model = MODELS[model_name](dim=1)
        _model.len_scale_bounds = len_scale_bounds
        try:
            _model.fit_variogram(_lags, _gamma, sill=1.0, nugget=nugget, weights=_pairs, loss="linear")
        except (RuntimeError, ValueError):
            return None
        _misfit = float(np.sqrt(np.average((_model.variogram(_lags) - _gamma) ** 2, weights=_pairs)))
        return _model.nugget, _model.len_scale, _misfit


    def _fit_both(model_name, points):
        """A model fitted to a domain's experimental variograms: the nugget from the vertical one, which has the
        short lags, and the horizontal one fitted with that nugget. Its misfit is the mean of the two
        directions' misfits."""
        _vertical = _fit(
            model_name, points.filter(pl.col("direction") == "vertical"), nugget=True, len_scale_bounds=LEN_SCALE_BOUNDS["vertical"]
        )
        _nugget = _vertical[0] if _vertical else 0.0
        _horizontal = _fit(
            model_name, points.filter(pl.col("direction") == "horizontal"), nugget=_nugget, len_scale_bounds=LEN_SCALE_BOUNDS["horizontal"]
        )
        _misfits = [_direction[2] for _direction in (_vertical, _horizontal) if _direction]
        return {
            "nugget": _nugget,
            "vertical": _vertical[1] if _vertical else None,
            "horizontal": _horizontal[1] if _horizontal else None,
            "misfit": float(np.mean(_misfits)) if _misfits else None,
        }


    # Per parameter, domain and model, the fitted model; and per parameter and domain, the model that misfits
    # least
    fitted = {
        _name: {
            _domain: {
                _model: _fit_both(_model, experimental.filter((pl.col("parameter") == _name) & (pl.col("domain") == _domain)))
                for _model in MODELS
            }
            for _domain in DOMAIN_COLORS
        }
        for _name in parameters.value
    }
    best_models = {
        _name: {
            _domain: min(
                (_model for _model, _fit in _fits.items() if _fit["misfit"] is not None),
                key=lambda _model: _fits[_model]["misfit"],
                default="Exponential",
            )
            for _domain, _fits in _domains.items()
        }
        for _name, _domains in fitted.items()
    }
    best_models
    return best_models, fitted


@app.cell
def saved_variograms(Path, json, variograms_json):
    # The variograms saved before, per parameter; empty until they are saved. Each parameter's carry when they
    # were saved and the date of the simulation domains they were fitted on: SAVE_DATES.
    SAVE_DATES = ("saved", "simulation_domains_saved")
    saved_variograms = json.loads(Path(variograms_json).read_text(encoding="utf-8")) if Path(variograms_json).exists() else {}
    return SAVE_DATES, saved_variograms


@app.cell(hide_code=True)
def variograms_intro(PARAMETERS, mo, parameters):
    reset_to_fit = mo.ui.run_button(label="Start again from the best fits")
    # Which parameter's variograms the rows show, when several are chosen
    _chosen = {_label: _name for _label, _name in PARAMETERS.items() if _name in parameters.value}
    shown_parameter = mo.ui.radio(_chosen, value=next(iter(_chosen)), inline=True, label="Show the variograms of")
    mo.vstack(
        [
            mo.md(r"""
    ## 2 · The variograms per domain

    Each row is one domain: its model and sliders, its vertical variogram along the CPTs and its horizontal
    one between CPTs at one level. The dots are the experimental variogram, as large as their number of
    pairs of samples, and faint below the number a lag needs to count in the fit. The line is the model of
    the sliders. Exponential, spherical and Gaussian models are each fitted by weighted least squares with a
    sill of 1, and a domain starts with the one that misfits least, unless the saved variograms are of this
    parameter and trend. Choosing another model for a domain starts its sliders from that model's fit. Both
    directions share the nugget. Each chosen parameter has its own models and sliders.
    """),
            mo.hstack([shown_parameter, reset_to_fit], justify="space-between") if len(_chosen) > 1 else reset_to_fit,
        ]
    )
    return reset_to_fit, shown_parameter


@app.cell(hide_code=True)
def model_choice(
    DOMAIN_COLORS,
    MODELS,
    best_models,
    detrend,
    mo,
    parameters,
    reset_to_fit,
    saved_variograms,
):
    def _start_model(name, domain):
        """A domain's model for one parameter: the saved one, when the saved variograms of the parameter have
        this trend; otherwise the best-fitting one"""
        _saved = saved_variograms.get(name, {})
        _use_saved = not reset_to_fit.value and _saved.get("detrend") == detrend.value
        _variogram = _saved.get("domains", {}).get(domain) if _use_saved else None
        return _variogram.get("model", _saved.get("model")) if _variogram else best_models[name][domain]


    model_choice = mo.ui.dictionary(
        {
            _name: mo.ui.dictionary(
                {_domain: mo.ui.dropdown(list(MODELS), value=_start_model(_name, _domain), label="Model") for _domain in DOMAIN_COLORS}
            )
            for _name in parameters.value
        }
    )
    return (model_choice,)


@app.cell(hide_code=True)
def moved_sliders(mo):
    # The sliders as they were last moved, per parameter with each domain's model, so that choosing another
    # model for one domain leaves the other domains' sliders where they are
    get_moved_sliders, set_moved_sliders = mo.state({})
    return get_moved_sliders, set_moved_sliders


@app.cell(hide_code=True)
def variogram_controls(
    DOMAIN_COLORS,
    LEN_SCALE_BOUNDS,
    detrend,
    fitted,
    get_moved_sliders,
    mo,
    model_choice,
    parameters,
    reset_to_fit,
    saved_variograms,
    set_moved_sliders,
):
    # Where a domain's sliders start for one parameter: where they were last moved with its model; otherwise
    # its saved variogram, when the saved variograms of the parameter have this trend and it has the same
    # model; otherwise that model's fit, or DEFAULTS where there is none
    DEFAULTS = {"nugget": 0.0, "vertical": 1.0, "horizontal": 100.0}
    _moved = {} if reset_to_fit.value else get_moved_sliders()
    if reset_to_fit.value:
        set_moved_sliders({})


    def _start(name, domain):
        _model = model_choice.value[name][domain]
        _last = _moved.get(name, {})
        _last = _last["domains"].get(domain, {}) if _last.get("detrend") == detrend.value else {}
        if _last.get("model") == _model:
            return _last
        _saved = saved_variograms.get(name, {})
        _use_saved = not reset_to_fit.value and _saved.get("detrend") == detrend.value
        _variogram = _saved.get("domains", {}).get(domain) if _use_saved else None
        if _variogram and _variogram.get("model", _saved.get("model")) == _model:
            return {"nugget": _variogram["nugget"], **_variogram["len_scale"]}
        _fit = fitted[name][domain][_model]
        return {_key: DEFAULTS[_key] if _fit[_key] is None else float(_fit[_key]) for _key in DEFAULTS}


    def _slider(bounds, step, value, label):
        _value = round(round(min(max(value, bounds[0]), bounds[1]) / step) * step, 2)
        return mo.ui.slider(start=bounds[0], stop=bounds[1], step=step, value=_value, show_value=True, label=label)


    def _sliders(start):
        return mo.ui.dictionary(
            {
                "nugget": _slider([0.0, 1.0], 0.01, start["nugget"], "Nugget"),
                "vertical": _slider(LEN_SCALE_BOUNDS["vertical"], 0.05, start["vertical"], "Vertical length scale (m)"),
                "horizontal": _slider(LEN_SCALE_BOUNDS["horizontal"], 5.0, start["horizontal"], "Horizontal length scale (m)"),
            }
        )


    def _remember(value):
        set_moved_sliders(
            {
                _name: {
                    "detrend": detrend.value,
                    "domains": {
                        _domain: {"model": model_choice.value[_name][_domain], **_values} for _domain, _values in _domains.items()
                    },
                }
                for _name, _domains in value.items()
            }
        )


    variogram_controls = mo.ui.dictionary(
        {
            _name: mo.ui.dictionary({_domain: _sliders(_start(_name, _domain)) for _domain in DOMAIN_COLORS})
            for _name in parameters.value
        },
        on_change=_remember,
    )
    return (variogram_controls,)


@app.cell(hide_code=True, expand_output=True)
def variogram_rows(
    DOMAIN_COLORS,
    MAX_LAG,
    MIN_PAIRS,
    MODELS,
    alt,
    best_models,
    experimental,
    fitted,
    mo,
    model_choice,
    np,
    pl,
    shown_parameter,
    trends,
    variogram_controls,
):
    def model_of(name, domain, direction):
        """The GSTools model of a domain's model and sliders for one parameter, in one direction"""
        _sliders = variogram_controls.value[name][domain]
        return MODELS[model_choice.value[name][domain]](
            dim=1, var=1.0 - _sliders["nugget"], len_scale=_sliders[direction], nugget=_sliders["nugget"]
        )


    def _chart(name, domain, direction):
        _lags = np.linspace(0, MAX_LAG[direction], 200)[1:]
        _curve = pl.DataFrame({"lag": _lags, "gamma": model_of(name, domain, direction).variogram(_lags)})
        _x = alt.X("lag:Q", title="Lag (m)", scale=alt.Scale(domain=[0, MAX_LAG[direction]]))
        _y = alt.Y("gamma:Q", title="Semivariance", scale=alt.Scale(domain=[0, 2], clamp=True))
        _points = (
            alt.Chart(
                experimental.filter(
                    (pl.col("parameter") == name) & (pl.col("domain") == domain) & (pl.col("direction") == direction)
                )
            )
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


    def _row(name, domain):
        _sliders = variogram_controls[name][domain]
        _trend = trends.filter((pl.col("parameter") == name) & (pl.col("domain") == domain)).row(0, named=True)
        _ranges = {_d: model_of(name, domain, _d).percentile_scale(0.95) for _d in ("vertical", "horizontal")}
        _misfits = " · ".join(
            f"{_model} {_fit['misfit']:.3f}" for _model, _fit in fitted[name][domain].items() if _fit["misfit"] is not None
        )
        _about = mo.md(
            f'<span style="display:inline-block;width:12px;height:12px;background:{DOMAIN_COLORS[domain]};'
            f'border:1px solid #999;margin-right:6px"></span>**{domain}**<br>'
            f"{_trend['cpts']} CPTs, {_trend['samples']} samples. 95 % of the sill at "
            f"{_ranges['vertical']:.1f} m vertically and {_ranges['horizontal']:.0f} m horizontally.<br>"
            f"Misfit of the fits: {_misfits}; {best_models[name][domain]} fits best."
        )
        return mo.vstack(
            [
                _about,
                mo.hstack(
                    [model_choice[name][domain], _sliders["nugget"], _sliders["vertical"], _sliders["horizontal"]],
                    justify="start",
                    gap=2,
                ),
                mo.hstack([_chart(name, domain, "vertical"), _chart(name, domain, "horizontal")], justify="start", gap=2),
            ]
        )


    mo.vstack([_row(shown_parameter.value, _domain) for _domain in DOMAIN_COLORS], gap=2)
    return (model_of,)


@app.cell(hide_code=True)
def variograms(
    DOMAIN_COLORS,
    mo,
    model_choice,
    model_of,
    pl,
    variogram_controls,
):
    # The variograms of the models and sliders, per parameter and domain, in GSTools' terms: the nugget and
    # the variance (the partial sill) add up to 1; a len_scale per direction
    variograms = pl.DataFrame(
        [
            {
                "parameter": _name,
                "domain": _domain,
                "model": model_choice.value[_name][_domain],
                "nugget": _sliders["nugget"],
                "variance": round(1.0 - _sliders["nugget"], 2),
                "len_scale vertical (m)": _sliders["vertical"],
                "len_scale horizontal (m)": _sliders["horizontal"],
                "anisotropy (vertical / horizontal)": round(_sliders["vertical"] / _sliders["horizontal"], 4),
                "95 % range vertical (m)": round(model_of(_name, _domain, "vertical").percentile_scale(0.95), 2),
                "95 % range horizontal (m)": round(model_of(_name, _domain, "horizontal").percentile_scale(0.95), 1),
            }
            for _name, _domains in variogram_controls.value.items()
            for _domain, _sliders in _domains.items()
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

    Saving pins the variograms of the chosen parameters for `04`. It writes them to
    `notebooks/variograms.json`, which is committed with the notebooks and keeps the saved variograms of
    the other parameters. Each parameter has its transform and, per domain, its model, nugget, length
    scales and trend, with the date it was saved and the date of the simulation domains it was fitted on.
    """)
    return


@app.cell(hide_code=True)
def variogram_definition(
    LOG_PARAMETERS,
    detrend,
    mo,
    model_choice,
    trends,
    variogram_controls,
):
    # The variograms of the chosen parameters as variograms.json holds them
    _trends = {(_row["parameter"], _row["domain"]): _row for _row in trends.iter_rows(named=True)}
    variogram_definitions = {
        _name: {
            "transform": "log10" if _name in LOG_PARAMETERS else "none",
            "detrend": detrend.value,
            "domains": {
                _domain: {
                    "model": model_choice.value[_name][_domain],
                    "nugget": _sliders["nugget"],
                    "len_scale": {"horizontal": _sliders["horizontal"], "vertical": _sliders["vertical"]},
                    # The trend of the transformed parameter: intercept + slope * z, z in m NAP
                    "trend": {"intercept": _trends[_name, _domain]["intercept"], "slope": _trends[_name, _domain]["slope"]},
                }
                for _domain, _sliders in _domains.items()
            },
        }
        for _name, _domains in variogram_controls.value.items()
    }
    save_variograms = mo.ui.run_button(label="Save these variograms")
    save_variograms
    return save_variograms, variogram_definitions


@app.cell(hide_code=True)
def saved_status(
    SAVE_DATES,
    domain_definition,
    json,
    mo,
    parameters,
    saved_variograms,
    variogram_definitions,
):
    def _status(name):
        """Whether the saved variograms of one parameter are the ones above, and fitted on the saved simulation
        domains"""
        _saved = saved_variograms.get(name)
        if _saved is None:
            return mo.callout(mo.md(f"No variograms of {name} are saved yet."), kind="warn")
        _when = _saved.get("saved", "an unknown date")
        if {_k: _v for _k, _v in _saved.items() if _k not in SAVE_DATES} != json.loads(json.dumps(variogram_definitions[name])):
            return mo.callout(mo.md(f"The variograms of {name} above differ from the ones saved on {_when}."), kind="warn")
        if _saved.get("simulation_domains_saved") != domain_definition["saved"]:
            return mo.callout(
                mo.md(
                    f"The variograms of {name} above are the ones saved on {_when}, but those were fitted on other "
                    "simulation domains. Save them again."
                ),
                kind="warn",
            )
        return mo.callout(mo.md(f"The variograms of {name} above are the ones saved on {_when}."), kind="success")


    mo.vstack([_status(_name) for _name in parameters.value])
    return


@app.cell(hide_code=True)
def save(
    PARAMETERS,
    VARIOGRAMS_JSON,
    datetime,
    domain_definition,
    json,
    mo,
    save_variograms,
    saved_variograms,
    variogram_definitions,
):
    mo.stop(not save_variograms.value)
    # The chosen parameters' variograms, each with this save's date and the simulation domains' date, and the
    # other parameters' variograms as they were saved before
    _dates = {"saved": datetime.now().isoformat(timespec="seconds"), "simulation_domains_saved": domain_definition["saved"]}
    VARIOGRAMS_JSON.write_text(
        json.dumps(
            {
                **{_key: _value for _key, _value in saved_variograms.items() if _key in PARAMETERS.values()},
                **{_name: {**_definition, **_dates} for _name, _definition in variogram_definitions.items()},
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
