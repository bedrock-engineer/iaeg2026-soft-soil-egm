# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "altair",
#     "d-geolib==2.0.0",
#     "d-geolib-plus==0.4.1",
#     "httpx",
#     "marimo>=0.25.2",
#     "numpy",
#     "polars",
#     "pyarrow",
#     "wigglystuff",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")

with app.setup:
    import numpy as np

    # kPa, the atmospheric pressure of the normalization, and kN/m³, the unit weight of water
    ATMOSPHERE = 100.0
    GAMMA_WATER = 9.81
    # kN/m³, the limits of the unit weights, as in GeoLibPlus
    GAMMA_LIMITS = (10.5, 22.0)
    # m, how far the groundwater lies below the ground, unless given: CEMS CPT Core's default
    GROUNDWATER_DEPTH = 1.0
    # Robertson's soil behavior types, the normalized SBTn zones of his chart
    SOIL_BEHAVIOR_TYPES = {
        1: "Sensitive fine-grained",
        2: "Organic soil",
        3: "Clay",
        4: "Silt mixture",
        5: "Sand mixture",
        6: "Sand",
        7: "Dense sand to gravelly sand",
        8: "Very stiff sand to clayey sand",
        9: "Very stiff fine-grained",
    }
    # Their colors, from peat's brown through clay's blue to sand's yellow
    SOIL_BEHAVIOR_COLORS = {
        1: "#d73027",
        2: "#8c6d31",
        3: "#2c7fb8",
        4: "#41ae76",
        5: "#c2e699",
        6: "#fee08b",
        7: "#fdae61",
        8: "#bdbdbd",
        9: "#636363",
    }



@app.function
def robertson(qc, fs, z, ground_level, groundwater_level=None, u2=None, cone_area_ratio=0.8, gamma_missing=18.0):
    """Robertson's soil behavior type of CPT values, from the top down along the last axis, all at once.

    qc, fs and u2 in MPa, z and the levels in m NAP. qc and fs have shape (..., depth); z has shape (depth,)
    from the top down; the levels are scalars or have the shape (...). Cells without qc or fs are NaN and
    weigh gamma_missing (kN/m³) in the vertical stress of those below them. Without u2, qt uses the
    hydrostatic pressure.

    - Unit weight: Robertson & Cabal (2010), within GAMMA_LIMITS.
    - Stresses: the unit weights added up from the ground, the pore pressure hydrostatic below the
      groundwater.
    - Qtn, Fr and Ic: Robertson (2009), n iterated; Qtn and Fr within the limits of his chart.
    - Zones 2 to 7 from Ic, and zones 1, 8 and 9 from their boundaries in the chart: Robertson (2010).

    Returns a dict of arrays of qc's shape: gamma and the stresses in kN/m³ and kPa, Qtn, Fr (%), Ic, n and
    zone, which is 0 where there is no value.
    """
    qc, fs, z = np.asarray(qc, dtype=float), np.asarray(fs, dtype=float), np.asarray(z, dtype=float)
    ground = np.asarray(ground_level, dtype=float)[..., None]
    groundwater = ground - GROUNDWATER_DEPTH if groundwater_level is None else np.asarray(groundwater_level, dtype=float)[..., None]
    hydrostatic = GAMMA_WATER * np.clip(groundwater - z, 0.0, None)
    pore_pressure = hydrostatic if u2 is None else np.asarray(u2, dtype=float) * 1000.0
    qt = np.clip(qc * 1000.0 + pore_pressure * (1.0 - cone_area_ratio), 1e-3, None)
    friction = fs * 1000.0

    with np.errstate(divide="ignore", invalid="ignore"):
        gamma = GAMMA_WATER * (0.27 * np.log10(friction / qt * 100.0) + 0.36 * np.log10(qt / ATMOSPHERE) + 1.236)
    gamma = np.clip(gamma, *GAMMA_LIMITS)
    # Fs of 0 has no logarithm: the lowest unit weight
    gamma = np.where(np.isneginf(gamma) | (friction <= 0.0), GAMMA_LIMITS[0], gamma)
    weight = np.where(np.isnan(gamma), gamma_missing, gamma)

    # Each value holds from halfway to the value above to halfway to the one below; the first from the ground
    middles = (z[:-1] + z[1:]) / 2.0
    tops = np.minimum(np.concatenate([np.broadcast_to(ground, (*qc.shape[:-1], 1)), np.broadcast_to(middles, (*qc.shape[:-1], len(middles)))], axis=-1), ground)
    bottoms = np.concatenate([tops[..., 1:], np.minimum(2.0 * z[-1:] - tops[..., -1:], ground)], axis=-1)
    above = np.cumsum(weight * (tops - bottoms), axis=-1) - weight * (tops - bottoms)
    total_stress = above + weight * np.clip(tops - z, 0.0, None)
    effective_stress = np.clip(total_stress - hydrostatic, 1.0, None)

    net = np.clip(qt - total_stress, 1e-3, None)
    fr = np.clip(friction / net * 100.0, 0.1, 10.0)
    n = np.ones_like(net)
    for _ in range(50):
        qtn = np.clip(net / ATMOSPHERE * (ATMOSPHERE / effective_stress) ** n, 1.0, 1000.0)
        ic = np.sqrt((3.47 - np.log10(qtn)) ** 2 + (np.log10(fr) + 1.22) ** 2)
        previous, n = n, np.minimum(0.381 * ic + 0.05 * effective_stress / ATMOSPHERE - 0.15, 1.0)
        if np.nanmax(np.abs(n - previous)) < 1e-3:
            break

    zone = np.select(
        [ic < 1.31, ic < 2.05, ic < 2.60, ic < 2.95, ic < 3.60, ic >= 3.60],
        [7, 6, 5, 4, 3, 2],
        default=0,
    )
    zone = np.where(qtn < 12.0 * np.exp(-1.4 * fr), 1, zone)
    shifted = fr - 1.0
    stiff_boundary = 0.005 * shifted - 0.0003 * shifted**2 - 0.002
    very_stiff = (fr > 1.5) & (stiff_boundary > 0.0) & (qtn > 1.0 / np.where(stiff_boundary > 0.0, stiff_boundary, np.inf))
    zone = np.where(very_stiff, np.where(fr < 4.5, 8, 9), zone)
    missing = np.isnan(qc) | np.isnan(fs)
    zone = np.where(missing, 0, zone)
    return {
        "gamma": np.where(missing, np.nan, gamma),
        "total_stress": total_stress,
        "effective_stress": effective_stress,
        "qtn": np.where(missing, np.nan, qtn),
        "fr": np.where(missing, np.nan, fr),
        "ic": np.where(missing, np.nan, ic),
        "n": np.where(missing, np.nan, n),
        "zone": zone,
    }


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Robertson classification of CPTs

    `robertson` classifies CPT values with Robertson's normalized soil behavior type (SBTn), for whole
    simulated grids at once: `05_cpt_classification.py` imports it. This notebook checks it on the measured
    CPTs against two other implementations, GeoLibPlus (Deltares) and CEMS CPT Core (through NUCLEI).

    All three get the same values: the CPTs' qc and fs from their BRO XML, without their measured u2, since
    the simulation has no u2 either, and groundwater 1 m below the ground, CEMS's default.
    """)
    return


@app.cell
def _():
    import json
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import polars as pl

    alt.data_transformers.disable_max_rows()
    return Path, alt, json, mo, pl


@app.cell
def inputs(Path, mo):
    DATA_DIR = Path(mo.notebook_dir()).parent / "data"
    CPT_XML_DIR = DATA_DIR / "cpt_xml"
    CPTS_PARQUET = DATA_DIR / "cpts.parquet"
    # What the comparison keeps, so that it need not be computed or requested again
    COMPARISON_DIR = DATA_DIR / "cpt_robertson"
    GEOLIBPLUS_PARQUET = COMPARISON_DIR / "geolibplus.parquet"
    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
    return CPTS_PARQUET, CPT_XML_DIR, GEOLIBPLUS_PARQUET


@app.cell
def read_cpts(CPTS_PARQUET, CPT_XML_DIR, pl):
    import logging

    from geolib_plus.bro_xml_cpt import BroXmlCpt

    logging.getLogger().setLevel(logging.ERROR)


    class _Cpt(BroXmlCpt):
        """GeoLibPlus 0.4.1's calculate_friction_nbr_if_not_available fails on a CPT with a qc or fs of 0, by
        assigning all readings to those that have both. The friction ratio where there are both, otherwise 0."""

        def calculate_friction_nbr_if_not_available(self):
            if self.friction_nbr is None:
                _both = (self.tip > 0) & (self.friction > 0)
                self.friction_nbr = np.divide(self.friction, self.tip, out=np.zeros(len(self.tip)), where=_both) * 100


    def read_cpt(bro_id):
        """A CPT as GeoLibPlus reads and preprocesses it from its BRO XML"""
        _cpt = _Cpt()
        _cpt.read(CPT_XML_DIR / f"{bro_id}.xml")
        _cpt.pre_process_data()
        return _cpt


    def _readings(bro_id):
        _cpt = read_cpt(bro_id)
        return pl.DataFrame(
            {
                "bro_id": bro_id,
                "depth": _cpt.depth,
                "z": _cpt.depth_to_reference,
                "qc": np.clip(_cpt.tip, 0.0, None),
                "fs": np.clip(_cpt.friction, 0.0, None),
                "ground_level": float(_cpt.local_reference_level),
            }
        )


    # The readings of the CPTs that 01 selected, from the top down
    BRO_IDS = pl.read_parquet(CPTS_PARQUET)["bro_id"].unique().sort().to_list()
    readings = pl.concat([_readings(_bro_id) for _bro_id in BRO_IDS]).with_row_index("reading")
    readings
    return BRO_IDS, read_cpt, readings


@app.cell
def ours(pl, readings):
    def _classified(cpt, **kwargs):
        _result = robertson(cpt["qc"].to_numpy(), cpt["fs"].to_numpy(), cpt["z"].to_numpy(), cpt["ground_level"][0], **kwargs)
        return cpt.select("reading").with_columns(pl.Series(_k, _v) for _k, _v in _result.items())


    _cpts = [_cpt for _, _cpt in readings.group_by("bro_id", maintain_order=True)]
    # Our classification of each reading, as 05 will use it; and with qt = qc, as GeoLibPlus normalizes
    ours = pl.concat([_classified(_cpt) for _cpt in _cpts])
    ours_with_qc = pl.concat([_classified(_cpt, u2=np.zeros(1)) for _cpt in _cpts])
    return ours, ours_with_qc


@app.cell(hide_code=True)
def geolibplus_intro(mo):
    mo.md(r"""
    ## GeoLibPlus

    GeoLibPlus 0.4.1 cannot be compared as it comes, for three reasons found on these CPTs:

    - `calculate_friction_nbr_if_not_available` fails on a CPT with a qc or fs of 0.
    - `stress_calc` takes the absolute value of the levels in m NAP, so that the pore pressure is 0 at every
      depth below a groundwater level under NAP. At 24 m depth, the effective stress is then the total stress:
      425 kPa instead of about 200 kPa.
    - `norm_calc` passes the friction ratio (%) to `n_iter` where it takes the sleeve friction (kPa), so that
      F stays at its lower limit while n is iterated, and n comes out too low.

    The cells below correct these, the last one optionally. It also normalizes with qc where Robertson (and our
    function) use qt. Its zones are the polygons of Robertson's chart, where ours follow from Ic and the
    boundaries of zones 1, 8 and 9.
    """)
    return


@app.cell
def geolibplus(BRO_IDS, GEOLIBPLUS_PARQUET, pl, read_cpt):
    import sys

    from geolib_plus.robertson_cpt_interpretation import RobertsonCptInterpretation


    class _WithPorePressure(RobertsonCptInterpretation):
        """The stresses with the levels in m NAP as they are, rather than their absolute values"""

        def stress_calc(self):
            super().stress_calc()
            _pore_pressure = np.clip(self.data.pwp - self.data.depth_to_reference, 0.0, None) * self.data.g
            self.data.effective_stress = np.clip(self.data.total_stress - _pore_pressure, 0.0, None)


    _module = sys.modules[RobertsonCptInterpretation.__module__]
    _n_iter = _module.n_iter


    def _interpreted(bro_id, n_corrected):
        """A CPT's classification; with n_corrected, n_iter gets the sleeve friction in kPa, as tip is then"""
        _cpt = read_cpt(bro_id)
        _interpreter = _WithPorePressure()
        _interpreter.user_defined_water_level = True
        _cpt.pwp = float(_cpt.local_reference_level) - GROUNDWATER_DEPTH
        _friction = _cpt.friction * 1000.0
        if n_corrected:
            _module.n_iter = lambda n, qt, friction_nb, sigma_eff, sigma_tot, Pa: _n_iter(n, qt, _friction, sigma_eff, sigma_tot, Pa)
        try:
            _cpt.interpret_cpt(_interpreter)
        finally:
            _module.n_iter = _n_iter
        return pl.DataFrame(
            {
                "bro_id": bro_id,
                "depth": _cpt.depth,
                "n_corrected": n_corrected,
                "gamma": _interpreter.gamma,
                "total_stress": _cpt.total_stress,
                "effective_stress": _cpt.effective_stress,
                "qtn": _cpt.Qtn,
                "fr": _cpt.Fr,
                "ic": _cpt.IC,
                "n": _cpt.n,
                "zone": [int(_zone) for _zone in _cpt.lithology],
            }
        )


    # GeoLibPlus's classification of each reading, with and without the correction of n, computed once
    if not GEOLIBPLUS_PARQUET.exists():
        pl.concat([_interpreted(_bro_id, _n_corrected) for _bro_id in BRO_IDS for _n_corrected in (False, True)]).write_parquet(GEOLIBPLUS_PARQUET)
    geolib_results = pl.read_parquet(GEOLIBPLUS_PARQUET)
    return (geolib_results,)


@app.cell
def compared(geolib_results, mo, ours, ours_with_qc, pl, readings):
    IC_BANDS = [1.31, 2.05, 2.60, 2.95, 3.60]


    def _with_geolib(our_values, n_corrected):
        """Each reading with our classification and GeoLibPlus's"""
        return readings.join(our_values, on="reading").join(
            geolib_results.filter(pl.col("n_corrected") == n_corrected).drop("n_corrected"),
            on=["bro_id", "depth"],
            suffix="_geolibplus",
        )


    def _agreement(label, frame):
        _difference = frame["ic"] - frame["ic_geolibplus"]
        _qtn = frame["qtn"] - frame["qtn_geolibplus"]
        return {
            "compared with": label,
            "same zone": round((frame["zone"] == frame["zone_geolibplus"]).mean(), 3),
            "same Ic band": round(float(np.mean(np.digitize(frame["ic"].to_numpy(), IC_BANDS) == np.digitize(frame["ic_geolibplus"].to_numpy(), IC_BANDS))), 3),
            "Ic difference, P5": round(_difference.quantile(0.05), 3),
            "P95": round(_difference.quantile(0.95), 3),
            "n, median difference": round((frame["n"] - frame["n_geolibplus"]).median(), 3),
            "Qtn difference, P5": round(_qtn.quantile(0.05), 2),
            "Qtn P95": round(_qtn.quantile(0.95), 2),
        }


    # Each reading with both classifications, with n corrected
    compared = _with_geolib(ours, True)
    mo.vstack(
        [
            mo.md("""
    Our function against GeoLibPlus, per reading, as each correction removes a difference. With n corrected
    and qt = qc, the numbers agree closely; what remains in the zones is mainly the polygons against Ic.
    """),
            pl.DataFrame(
                [
                    _agreement("GeoLibPlus without the correction of n", _with_geolib(ours, False)),
                    _agreement("GeoLibPlus with n corrected", compared),
                    _agreement("GeoLibPlus with n corrected, ours with qt = qc", _with_geolib(ours_with_qc, True)),
                ]
            ),
        ]
    )
    return (compared,)


@app.cell
def zone_matrix(alt, compared, pl):
    # With CPT Core's zone 0, which is not on Robertson's chart
    _labels = {0: "0 No zone (CPT Core)"} | {_zone: f"{_zone} {_name}" for _zone, _name in SOIL_BEHAVIOR_TYPES.items()}
    _order = list(_labels.values())


    def zone_matrix_chart(frame, column, label):
        """The readings per zone of ours against another classification's"""
        _counts = frame.group_by("zone", column).len().with_columns(
            pl.col("zone").replace_strict(_labels, return_dtype=pl.String).alias("ours"),
            pl.col(column).replace_strict(_labels, return_dtype=pl.String).alias(label),
        )
        _base = alt.Chart(_counts).encode(
            x=alt.X(f"{label}:N", sort=_order, scale=alt.Scale(domain=_order), axis=alt.Axis(labelAngle=-40)),
            y=alt.Y("ours:N", sort=_order, scale=alt.Scale(domain=_order)),
        )
        return (
            _base.mark_rect().encode(
                color=alt.Color("len:Q", scale=alt.Scale(type="log", scheme="blues"), legend=None), tooltip=["ours", label, "len"]
            )
            + _base.mark_text(fontSize=11).encode(text="len:Q")
        ).properties(width=430, height=330, title=f"Readings per zone: ours against {label}")


    zone_matrix_chart(compared, "zone_geolibplus", "GeoLibPlus")
    return (zone_matrix_chart,)


@app.cell
def cpt_choice(BRO_IDS, mo, readings):
    _longest = readings.group_by("bro_id").len().sort("len")["bro_id"][-1]
    shown_cpt = mo.ui.dropdown(BRO_IDS, value=_longest, label="CPT", searchable=True)
    shown_cpt
    return (shown_cpt,)


@app.cell
def profile(alt, compared, pl, shown_cpt):
    _cpt = compared.filter(pl.col("bro_id") == shown_cpt.value).sort("z", descending=True)
    _y = alt.Y("z:Q", title="z (m NAP)", scale=alt.Scale(zero=False))
    _ic = _cpt.unpivot(on=["ic", "ic_geolibplus"], index="z", variable_name="method", value_name="Ic").with_columns(
        pl.col("method").replace_strict({"ic": "ours", "ic_geolibplus": "GeoLibPlus"})
    )
    _lines = alt.Chart(_ic).mark_line(strokeWidth=1).encode(x=alt.X("Ic:Q", scale=alt.Scale(domain=[1, 4.5], clamp=True)), y=_y, color="method:N", order="z:Q")
    _zones = _cpt.unpivot(on=["zone", "zone_geolibplus"], index="z", variable_name="method", value_name="number").with_columns(
        pl.col("method").replace_strict({"zone": "ours", "zone_geolibplus": "GeoLibPlus"}),
        pl.col("number").replace_strict(SOIL_BEHAVIOR_TYPES, return_dtype=pl.String).alias("soil behavior type"),
    )
    _strip = (
        alt.Chart(_zones)
        .mark_tick(thickness=3, size=28, orient="vertical")
        .encode(
            x=alt.X("method:N", title=None),
            y=_y,
            color=alt.Color(
                "soil behavior type:N",
                scale=alt.Scale(domain=list(SOIL_BEHAVIOR_TYPES.values()), range=list(SOIL_BEHAVIOR_COLORS.values())),
            ),
        )
    )
    alt.hconcat(_lines.properties(width=320, height=480), _strip.properties(width=120, height=480)).resolve_scale(color="independent")
    return


@app.cell(hide_code=True)
def cems_intro(mo):
    mo.md(r"""
    ## CEMS CPT Core

    CPT Core wants a NUCLEI access token in `NUCLEI_TOKEN`: it is read from the environment, or paste one from
    the NUCLEI *API Access Tokens* page below. It is not saved. Each CPT's request and raw response are saved in
    `data/cpt_robertson/cems/` with the API's version, so that a CPT is requested once.

    CPT Core merges the readings into layers, each with a zone number and no Ic, and its layers depend on its
    settings and version. So the comparison is of zones: per reading, by the layer it lies in, and per layer, by
    the zone most of its readings have in the other classification.
    """)
    return


@app.cell
def cems_access(GEOLIBPLUS_PARQUET, mo):
    import httpx
    from wigglystuff import EnvConfig

    CPT_CORE_URL = "https://crux-nuclei.com/api/cptcore/v1"
    CEMS_DIR = GEOLIBPLUS_PARQUET.parent / "cems"


    def _check_nuclei_token(token):
        """Raises unless CPT Core accepts the token: the Robertson chart's default table computes nothing"""
        httpx.get(f"{CPT_CORE_URL}/classify/robertson", headers={"Authorization": f"Bearer {token}"}, timeout=30).raise_for_status()


    nuclei_config = mo.ui.anywidget(EnvConfig({"NUCLEI_TOKEN": _check_nuclei_token}))
    cems_classify = mo.ui.run_button(label="Classify the CPTs with CEMS CPT Core")
    mo.vstack([nuclei_config, cems_classify])
    return CEMS_DIR, CPT_CORE_URL, cems_classify, httpx, nuclei_config


@app.cell
def cems_run(
    BRO_IDS,
    CEMS_DIR,
    CPT_CORE_URL,
    cems_classify,
    httpx,
    json,
    mo,
    nuclei_config,
    pl,
    readings,
):
    def _saved_status(bro_id):
        """The status of a CPT's saved response, or None"""
        _path = CEMS_DIR / f"{bro_id}.json"
        return json.loads(_path.read_text(encoding="utf-8"))["status"] if _path.exists() else None


    def _classify(bro_id, cpt, token, version):
        """The CPT's request and raw response, saved as soon as they arrive; the token is in neither. The
        depths are GeoLibPlus's, corrected for inclination, with the readings it fills in over a predrilled top.
        Without u2 and a groundwater level, CPT Core uses the hydrostatic pressure and groundwater 1 m below the
        ground, as ours."""
        _request = {
            "data": {
                "correctedPenetrationLength": cpt["depth"].to_list(),
                "coneResistance": cpt["qc"].to_list(),
                "localFriction": cpt["fs"].to_list(),
            }
        }
        _response = httpx.post(
            f"{CPT_CORE_URL}/classify/robertson", json=_request, headers={"Authorization": f"Bearer {token}"}, timeout=300
        )
        (CEMS_DIR / f"{bro_id}.json").write_text(
            json.dumps({"api_version": version, "request": _request, "status": _response.status_code, "response": _response.text}),
            encoding="utf-8",
        )


    # The CPTs without a good response, requested when the button is pressed
    _missing = [_bro_id for _bro_id in BRO_IDS if _saved_status(_bro_id) != 200]
    if cems_classify.value and _missing:
        try:
            _token = nuclei_config.widget["NUCLEI_TOKEN"]
        except KeyError:
            mo.stop(True, mo.md("Set `NUCLEI_TOKEN` above first."))
        CEMS_DIR.mkdir(exist_ok=True)
        _version = httpx.get(f"{CPT_CORE_URL}/openapi.json", timeout=30).json()["info"]["version"]
        for _bro_id in mo.status.progress_bar(_missing, title="Classifying with CEMS CPT Core"):
            _classify(_bro_id, readings.filter(pl.col("bro_id") == _bro_id), _token, _version)
    # What the cells below read
    cems_failed = [_bro_id for _bro_id in BRO_IDS if _saved_status(_bro_id) not in (200, None)]
    cems_saved = [_bro_id for _bro_id in BRO_IDS if _saved_status(_bro_id) == 200]
    mo.md(
        f"{len(cems_saved)} of {len(BRO_IDS)} CPTs have a saved response from CPT Core"
        + (f"; these failed: {', '.join(cems_failed)}." if cems_failed else ".")
    )
    return (cems_saved,)


@app.cell
def cems_compared(CEMS_DIR, cems_saved, compared, json, mo, pl):
    def _layers(bro_id):
        _saved = json.loads((CEMS_DIR / f"{bro_id}.json").read_text(encoding="utf-8"))
        _response = json.loads(_saved["response"])
        return pl.DataFrame(
            {
                "bro_id": bro_id,
                "top": _response["upperBoundary"],
                "bottom": _response["lowerBoundary"],
                "zone_cems": _response["soilBehaviorTypeIndex"],
                "name_cems": _response["soilBehaviorTypeName"],
            },
            schema_overrides={"zone_cems": pl.Int64},
        ).with_row_index("layer")


    mo.stop(not cems_saved, mo.md("The comparison with CPT Core follows from its saved responses."))
    # Each reading of the CPTs with a response, with the layer it lies in
    cems_layers = pl.concat([_layers(_bro_id) for _bro_id in cems_saved])
    compared_cems = (
        compared.filter(pl.col("bro_id").is_in(cems_saved))
        .sort("depth")
        .join_asof(cems_layers.sort("top"), left_on="depth", right_on="top", by="bro_id", strategy="backward", check_sortedness=False)
        .filter(pl.col("depth") <= pl.col("bottom"))
    )


    def _per_reading(column):
        return round((compared_cems[column] == compared_cems["zone_cems"]).mean(), 3)


    def _per_layer(column):
        """The share of layers, and of their thickness, whose zone is the one most of their readings have"""
        _layer = (
            compared_cems.group_by("bro_id", "layer")
            .agg(pl.col(column).mode().sort().first().alias("most"), pl.first("zone_cems"), (pl.first("bottom") - pl.first("top")).alias("thickness"))
            .with_columns(same=pl.col("most") == pl.col("zone_cems"))
        )
        return round(_layer["same"].mean(), 3), round(_layer.filter("same")["thickness"].sum() / _layer["thickness"].sum(), 3)


    mo.vstack(
        [
            mo.md(
                f"Against CPT Core, on {len(cems_saved)} CPTs: {compared_cems.height} of "
                f"{compared.filter(pl.col('bro_id').is_in(cems_saved)).height} readings lie in one of its "
                f"{cems_layers.height} layers."
            ),
            pl.DataFrame(
                [
                    {
                        "classification": _label,
                        "same zone, per reading": _per_reading(_column),
                        "per layer": _per_layer(_column)[0],
                        "per thickness of layer": _per_layer(_column)[1],
                    }
                    for _label, _column in (("ours", "zone"), ("GeoLibPlus, n corrected", "zone_geolibplus"))
                ]
            ),
        ]
    )
    return (compared_cems,)


@app.cell(hide_code=True)
def cems_note(mo):
    mo.md(r"""
    Most of the difference with CPT Core is its zones 8 and 9, marked as overconsolidated or cemented. It gives
    them to readings with a median Fr of 1.2–1.8 % and Qtn of 46–134, far below their boundary in Robertson's chart,
    where our function and GeoLibPlus's polygons have sand and sand mixtures. Where neither has zone 0, 8 or 9, the
    zones agree about as well as with GeoLibPlus. Its zone 0 is "Not defined". Why it assigns 8 and 9 this way
    does not follow from its documentation.
    """)
    return


@app.cell
def cems_matrix(compared_cems, zone_matrix_chart):
    zone_matrix_chart(compared_cems, "zone_cems", "CPT Core")
    return


@app.cell
def cems_profile(alt, compared_cems, mo, pl, shown_cpt):
    _cpt = compared_cems.filter(pl.col("bro_id") == shown_cpt.value)
    mo.stop(_cpt.is_empty(), mo.md(f"{shown_cpt.value} has no saved response from CPT Core."))
    _zones = _cpt.unpivot(on=["zone", "zone_geolibplus", "zone_cems"], index="z", variable_name="method", value_name="number").with_columns(
        pl.col("method").replace_strict({"zone": "ours", "zone_geolibplus": "GeoLibPlus", "zone_cems": "CPT Core"}),
        pl.col("number").replace_strict(SOIL_BEHAVIOR_TYPES, return_dtype=pl.String).alias("soil behavior type"),
    )
    (
        alt.Chart(_zones)
        .mark_tick(thickness=3, size=40, orient="vertical")
        .encode(
            x=alt.X("method:N", title=None, sort=["ours", "GeoLibPlus", "CPT Core"]),
            y=alt.Y("z:Q", title="z (m NAP)", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "soil behavior type:N",
                scale=alt.Scale(domain=list(SOIL_BEHAVIOR_TYPES.values()), range=list(SOIL_BEHAVIOR_COLORS.values())),
            ),
        )
        .properties(width=240, height=480, title=f"{shown_cpt.value}: the zones of the three classifications")
    )
    return


if __name__ == "__main__":
    app.run()
