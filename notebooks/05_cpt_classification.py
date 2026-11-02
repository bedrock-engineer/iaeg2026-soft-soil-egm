# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair",
#     "anywidget==0.11.0",
#     "h5netcdf==1.8.2",
#     "h5py==3.16.0",
#     "marimo>=0.25.2",
#     "marimo-lens==0.2.4",
#     "numpy",
#     "polars==2.1.0",
#     "pyarrow",
#     "traitlets==5.16.1",
#     "xarray==2026.9.0",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # CPT classification

    The soil behavior type of the simulated cells: each realization of a run from `04_simulation.py` classified with
    Robertson's normalized soil behavior type (SBTn), with the `robertson` function that
    `cpt_robertson_classification.py` checks against GeoLibPlus and CEMS CPT Core. Each realization's qc and fs
    are classified together, not their medians: the Ic of a median qc and a median fs is not the median Ic,
    and the realizations are what keeps qc and fs related (fs is co-simulated with qc). The share of the
    realizations in each zone is that zone's probability in the cell.

    A soil behavior type is what a CPT can tell: how the soil behaves under the cone, not what it is made of,
    which is what GeoTOP's lithology classes describe. A cell holds one qc and one fs per realization, so layers thinner than a cell do not show.
    """)
    return


@app.cell
def _():
    import hashlib
    import json
    from datetime import datetime
    from pathlib import Path

    import altair as alt
    import anywidget
    import marimo as mo
    import numpy as np
    import polars as pl
    import traitlets
    import xarray as xr
    from marimo_lens import Lens

    from cpt_robertson_classification import GROUNDWATER_DEPTH, SOIL_BEHAVIOR_COLORS, SOIL_BEHAVIOR_TYPES, robertson

    # The charts take tens of thousands of cells
    alt.data_transformers.disable_max_rows()
    return (
        GROUNDWATER_DEPTH,
        Lens,
        Path,
        SOIL_BEHAVIOR_COLORS,
        SOIL_BEHAVIOR_TYPES,
        alt,
        anywidget,
        datetime,
        hashlib,
        json,
        mo,
        np,
        pl,
        robertson,
        traitlets,
        xr,
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
    # What 02, 03 and 04 save, and where the classifications are saved
    SIMULATIONS_DIR = DATA_DIR / "simulations"
    CLASSIFICATIONS_DIR = DATA_DIR / "cpt_classification"
    domains_json = mo.watch.file(Path(mo.notebook_dir()) / "simulation_domains.json")
    variograms_json = mo.watch.file(Path(mo.notebook_dir()) / "variograms.json")
    voxels_parquet = mo.watch.file(DATA_DIR / "voxel_domains.parquet")
    # m, GeoTOP's columns and the height of its voxels; kN/m³, the unit weight of what lies above the
    # simulation domains and of what lacks a value
    COLUMN = 100.0
    VOXEL = 0.5
    GAMMA_MISSING = 18.0
    return (
        CLASSIFICATIONS_DIR,
        COLUMN,
        DATA_DIR,
        GAMMA_MISSING,
        SIMULATIONS_DIR,
        VOXEL,
        domains_json,
        variograms_json,
        voxels_parquet,
    )


@app.cell(hide_code=True)
def read_inputs(
    Path,
    SOIL_BEHAVIOR_TYPES,
    VOXEL,
    domains_json,
    json,
    mo,
    pl,
    variograms_json,
    voxels_parquet,
):
    mo.stop(
        not all(Path(_f).exists() for _f in (domains_json, variograms_json, voxels_parquet)),
        mo.md("Save the simulation domains in `02_simulation_domains.py` and the variograms in `03_variograms.py` first."),
    )
    domain_definition = json.loads(Path(domains_json).read_text(encoding="utf-8"))
    saved_variograms = json.loads(Path(variograms_json).read_text(encoding="utf-8"))
    DOMAIN_COLORS = domain_definition["colors"]
    # All GeoTOP voxels
    voxels = pl.read_parquet(Path(voxels_parquet))
    # The ground per GeoTOP column: the top of its highest voxel
    ground_levels = voxels.group_by("x", "y").agg((pl.col("z").max() + VOXEL / 2).alias("ground_level"))
    ZONE_LABELS = {_zone: f"{_zone} {_name}" for _zone, _name in SOIL_BEHAVIOR_TYPES.items()}
    return (
        DOMAIN_COLORS,
        ZONE_LABELS,
        domain_definition,
        ground_levels,
        saved_variograms,
        voxels,
    )


@app.cell(hide_code=True)
def run_intro(GROUNDWATER_DEPTH, mo):
    mo.md(rf"""
    ## 1 · The classification

    The table lists the saved runs with fs co-simulated with qc, the latest first; a run without that has
    realizations in which qc and fs do not belong together. The selected run is classified once and saved
    in `data/cpt_classification/`, as NetCDF on the run's grid: per cell the probability of each zone, the
    most likely zone and the P10, P50 and P90 of Ic. Where two zones are equally likely, the most likely is
    the lowest-numbered.

    The stresses need a ground level everywhere, which only GeoTOP gives: the top of each GeoTOP column.
    At the CPTs, this keeps 96 % of the zones they get with their own reference level, and 90 % in the top
    5 m. What lies between the ground and the simulation domains weighs 18 kN/m³. Groundwater lies
    {GROUNDWATER_DEPTH:g} m below the ground and the pore pressure is hydrostatic, as in the check of `robertson`.
    """)
    return


@app.cell(hide_code=True)
def saved_runs(
    SIMULATIONS_DIR,
    domain_definition,
    json,
    mo,
    pl,
    saved_variograms,
    xr,
):
    # The runs with fs co-simulated with qc. A run has current inputs when its variograms and simulation
    # domains are the ones saved now.
    _domains_now = {_k: _v for _k, _v in domain_definition.items() if _k != "saved"}


    def _current(definition):
        _at_height = saved_variograms.get(f"{definition['resolution']['vertical']:g}", {})
        return definition["simulation_domains"] == _domains_now and all(
            _variograms == {_k: _v for _k, _v in _at_height.get(_name, {}).items() if _k not in ("saved", "simulation_domains_saved")}
            for _name, _variograms in definition["variograms"].items()
        )


    _rows = []
    for _path in SIMULATIONS_DIR.glob("*.nc"):
        with xr.open_dataset(_path, engine="h5netcdf") as _dataset:
            _definition = json.loads(_dataset.attrs["definition"])
            if "fs" in _definition.get("cosimulated", {}):
                _rows.append(
                    {
                        "horizontal (m)": _definition["resolution"]["horizontal"],
                        "vertical (m)": _definition["resolution"]["vertical"],
                        "realizations": _definition["realizations"],
                        "seed": _definition["seed"],
                        "current inputs": _current(_definition),
                        "created": _dataset.attrs["created"],
                        "file": _path.name,
                    }
                )
    mo.stop(not _rows, mo.md("Simulate qc and fs in `04_simulation.py` first."))
    saved_runs = mo.ui.table(
        pl.DataFrame(_rows).sort("created", descending=True),
        selection="single",
        initial_selection=[0],
        label="Saved runs with fs co-simulated with qc",
    )
    saved_runs
    return (saved_runs,)


@app.cell(hide_code=True)
def classify(
    CLASSIFICATIONS_DIR,
    COLUMN,
    DOMAIN_COLORS,
    GAMMA_MISSING,
    GROUNDWATER_DEPTH,
    SIMULATIONS_DIR,
    SOIL_BEHAVIOR_TYPES,
    datetime,
    ground_levels,
    hashlib,
    json,
    mo,
    np,
    robertson,
    saved_runs,
    xr,
):
    mo.stop(saved_runs.value.is_empty(), mo.md("Select a run in the table above."))
    # Raise when the classification changes, so that those saved before are not reused
    CLASSIFICATION_VERSION = 1
    _run_path = SIMULATIONS_DIR / saved_runs.value["file"][0]
    # Everything that decides a classification; the hash of it is part of its file's name
    _definition = {
        "version": CLASSIFICATION_VERSION,
        "run": _run_path.name,
        "ground_level": "top of the GeoTOP column",
        "groundwater_depth": GROUNDWATER_DEPTH,
        "gamma_missing": GAMMA_MISSING,
    }
    _key = hashlib.sha256(json.dumps(_definition, sort_keys=True).encode()).hexdigest()[:12]
    classification_path = CLASSIFICATIONS_DIR / f"{_run_path.stem}_{_key}.nc"


    def _classify():
        """Each realization of the run classified, and per cell the probability of each zone, the most likely
        zone and the P10, P50 and P90 of Ic, saved as NetCDF on the run's grid. Written to a temporary file
        first, so that an interrupted save leaves no classification behind."""
        _started = datetime.now()
        _zones = np.array(list(SOIL_BEHAVIOR_TYPES))
        _by_column = {(_x, _y): _level for _x, _y, _level in ground_levels.iter_rows()}
        with xr.open_dataset(_run_path, engine="h5netcdf") as _run:
            _x, _y, _z = (_run[_axis].values for _axis in ("x", "y", "z"))
            _domains = _run["domain"].fillna(-1).values.astype(np.int8)
            _realizations = _run.sizes["realization"]
            _shape = _domains.shape
            # The ground per cell column, of the GeoTOP column it lies in; no cells where there is none
            _ground = np.array(
                [[_by_column.get((_cx // COLUMN * COLUMN, _cy // COLUMN * COLUMN), 0.0) for _cx in _x] for _cy in _y]
            )
            _counts = np.zeros((len(_zones), *_shape), dtype=np.int32)
            _ic = np.full((_realizations, *_shape), np.nan, dtype=np.float32)
            # The run's grid is z × y × x with z going up; robertson takes the last axis from the top down
            _top_down = lambda _values: np.moveaxis(_values, 0, -1)[..., ::-1]
            _back = lambda _values: np.moveaxis(_values[..., ::-1], -1, 0)
            for _r in mo.status.progress_bar(range(_realizations), title="Classifying", show_eta=True):
                _result = robertson(
                    _top_down(_run["qc"].isel(realization=_r).values),
                    _top_down(_run["fs"].isel(realization=_r).values),
                    _z[::-1],
                    _ground,
                    gamma_missing=GAMMA_MISSING,
                )
                _zone = _back(_result["zone"])
                _ic[_r] = _back(_result["ic"])
                for _k, _number in enumerate(_zones):
                    _counts[_k] += _zone == _number
        _inside = _domains >= 0
        _probabilities = np.where(_inside, _counts / _realizations, np.nan).astype(np.float32)
        _most_likely = np.where(_inside, _zones[_counts.argmax(axis=0)], 0).astype(np.int8)
        _percentiles = np.full((3, *_shape), np.nan, dtype=np.float32)
        _percentiles[:, _inside] = np.percentile(_ic[:, _inside], [10, 50, 90], axis=0)
        _dataset = xr.Dataset(
            {
                "zone_probability": (("zone", "z", "y", "x"), _probabilities, {"description": "Share of the realizations in each SBTn zone"}),
                "most_likely_zone": (("z", "y", "x"), _most_likely, {"description": "The most likely SBTn zone, 0 outside the simulation domains"}),
                **{
                    f"ic_p{_p}": (("z", "y", "x"), _values, {"description": f"P{_p} of the realizations' Ic"})
                    for _p, _values in zip((10, 50, 90), _percentiles)
                },
                "domain": (
                    ("z", "y", "x"),
                    _domains,
                    {"flag_values": list(range(len(DOMAIN_COLORS))), "flag_meanings": " ".join(DOMAIN_COLORS), "missing_value": -1},
                ),
            },
            coords={"zone": _zones, "z": _z, "y": _y, "x": _x},
            attrs={
                "definition": json.dumps(_definition, ensure_ascii=False),
                "soil_behavior_types": json.dumps(SOIL_BEHAVIOR_TYPES, ensure_ascii=False),
                "crs": "EPSG:28992 (RD New), z in m NAP",
                "created": datetime.now().isoformat(timespec="seconds"),
                "seconds": round((datetime.now() - _started).total_seconds(), 1),
            },
        )
        classification_path.parent.mkdir(parents=True, exist_ok=True)
        _temporary = classification_path.with_suffix(".nc.tmp")
        _dataset.to_netcdf(
            _temporary,
            engine="h5netcdf",
            encoding={_name: {"zlib": True, "complevel": 4} for _name in _dataset.data_vars},
        )
        _temporary.replace(classification_path)


    if classification_path.exists():
        _report = f"This run was classified before, as `{classification_path.name}`."
    else:
        _classify()
        _report = f"Classified the run and saved it as `{classification_path.name}`."
    mo.md(_report)
    return (classification_path,)


@app.cell(hide_code=True)
def classified(
    DATA_DIR,
    classification_path,
    mo,
    np,
    pl,
    saved_runs,
    voxels,
    xr,
):
    # The selected run's classification at its cells (where the grid has a domain): the probabilities as
    # zones × cells, the most likely zone and its probability, and Ic's percentiles
    with xr.open_dataset(classification_path, engine="h5netcdf") as _dataset:
        _domains = _dataset["domain"].fillna(-1).values.astype(int)
        _names = np.array(_dataset["domain"].attrs["flag_meanings"].split())
        _iz, _iy, _ix = np.nonzero(_domains >= 0)
        zone_numbers = _dataset["zone"].values
        zone_probabilities = _dataset["zone_probability"].values[:, _iz, _iy, _ix]
        most_likely = _dataset["most_likely_zone"].values[_iz, _iy, _ix].astype(int)
        ic = {_p: _dataset[f"ic_{_p}"].values[_iz, _iy, _ix] for _p in ("p10", "p50", "p90")}
        _coords = {_axis: _dataset[_axis].values for _axis in ("x", "y", "z")}
    most_likely_probability = zone_probabilities[most_likely - 1, np.arange(len(most_likely))]
    cell_size = {
        "x": saved_runs.value["horizontal (m)"][0],
        "y": saved_runs.value["horizontal (m)"][0],
        "z": saved_runs.value["vertical (m)"][0],
    }
    # The CPT samples that 03 saved at the run's vertical resolution
    SAMPLE_HEIGHT = cell_size["z"]
    _samples_path = DATA_DIR / f"simulation_samples_{SAMPLE_HEIGHT * 100:g}cm.parquet"
    mo.stop(not _samples_path.exists(), mo.md("Save the variograms of this run's vertical resolution in `03_variograms.py` first."))
    samples = pl.read_parquet(_samples_path)
    # Each cell with the stratigraphic unit and lithology class of the GeoTOP voxel it lies in (a voxel's x
    # and y are its south-west corner, its z its center)
    cells = (
        pl.DataFrame(
            {
                "x": _coords["x"][_ix],
                "y": _coords["y"][_iy],
                "z": _coords["z"][_iz],
                "domain": _names[_domains[_iz, _iy, _ix]],
            }
        )
        .with_row_index("cell")
        .with_columns(
            voxel_x=(pl.col("x") // 100) * 100, voxel_y=(pl.col("y") // 100) * 100, voxel_z=(pl.col("z") / 0.5).round() * 0.5
        )
        .join(
            voxels.select(voxel_x="x", voxel_y="y", voxel_z="z", stratigraphic_unit="stratigraphic_unit", grondsoort="grondsoort"),
            on=["voxel_x", "voxel_y", "voxel_z"],
            how="left",
            maintain_order="left",
        )
        .with_columns(pl.col("stratigraphic_unit", "grondsoort").fill_null("unknown"))
    )
    return (
        SAMPLE_HEIGHT,
        cell_size,
        cells,
        ic,
        most_likely,
        most_likely_probability,
        samples,
        zone_numbers,
        zone_probabilities,
    )


@app.cell(hide_code=True)
def view_intro(mo):
    mo.md(r"""
    ## 2 · The soil behavior types

    The selected run's cells from above at one level, with a west–east section above and a south–north section to
    the right, as in `04`: drag the red dot in the plan to move the sections, and drag in either section to
    change the plan's level. Color the cells by their most likely SBTn zone, by how likely that zone is, by the
    probability of one SBTn zone, by the median of Ic or its spread, P90 − P10, or by their simulation domain.
    Hover over a cell for its zone and how likely it is. Click a CPT in the plan to show it below the sections
    in its column of cells: Ic of the realizations, the probabilities of the zones and the zones of the CPT
    samples, which are classified the same way as the cells (section 3).
    """)
    return


@app.cell(hide_code=True)
def cross_sections_widget(Path, anywidget, mo, traitlets):
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
def view_controls(ZONE_LABELS, mo, zone_numbers, zone_probabilities):
    # The zones that occur in some realization, for the probability of one of them
    _occurring = [int(_zone) for _zone, _probabilities in zip(zone_numbers, zone_probabilities) if _probabilities.max() > 0]
    color_by = mo.ui.radio(
        {
            "Most likely SBTn": "most likely",
            "Its probability": "its probability",
            "SBTn probability": "probability",
            "Ic median": "ic median",
            "Ic spread": "ic spread",
            "Simulation domain": "domain",
        },
        value="Most likely SBTn",
        label="Color by",
        inline=True,
    )
    probability_of = mo.ui.dropdown(
        {ZONE_LABELS[_zone]: _zone for _zone in _occurring},
        value=ZONE_LABELS[3 if 3 in _occurring else _occurring[0]],
        label="SBTn zone",
    )
    return color_by, probability_of


@app.cell(hide_code=True)
def color_controls(color_by, mo, probability_of):
    # The zone can only be chosen when the cells show its probability
    mo.vstack([color_by, probability_of] if color_by.value == "probability" else [color_by])
    return


@app.cell(hide_code=True, expand_output=True)
def cross_sections(
    CrossSections,
    DOMAIN_COLORS,
    SOIL_BEHAVIOR_COLORS,
    ZONE_LABELS,
    cell_size,
    cells,
    mo,
    most_likely,
    np,
    pl,
    samples,
):
    # Made once per selected run; section_values colors it. The zones that are most likely somewhere, with
    # their colors, and the stratigraphic units from the top down, by name for the cell under the pointer.
    _zones = np.unique(most_likely).tolist()
    _zone_index = np.searchsorted(_zones, most_likely)
    _units = cells.group_by("stratigraphic_unit").agg(pl.max("z")).sort("z", descending=True)["stratigraphic_unit"].to_list()
    _cpts = samples.sort("z", descending=True).group_by("bro_id", maintain_order=True).agg(pl.first("x", "y"), "z", "qc")
    _corners = cells.select(
        (pl.col("x") - cell_size["x"] / 2).round(3),
        (pl.col("y") - cell_size["y"] / 2).round(3),
        "z",
        pl.col("stratigraphic_unit").replace_strict({_u: _i for _i, _u in enumerate(_units)}, return_dtype=pl.Int64),
        pl.Series("zone", _zone_index, dtype=pl.Int64),
        pl.col("domain").replace_strict({_d: _i for _i, _d in enumerate(DOMAIN_COLORS)}, default=-1, return_dtype=pl.Int64),
    )
    # The sections start through the cell with the most CPTs, at the CPT samples' median level
    _origin = {_axis: _corners[_axis].min() for _axis in ("x", "y")}
    _start = (
        samples.select(
            *((_origin[_a] + ((pl.col(_a) - _origin[_a]) // cell_size[_a]) * cell_size[_a]).round(3).alias(_a) for _a in ("x", "y")),
            "bro_id",
        )
        .group_by("x", "y")
        .agg(pl.n_unique("bro_id"))
        .sort("bro_id", descending=True)
        .row(0)
    )
    _levels = cells["z"].unique().to_list()
    # The CPT with the most samples is selected first
    _selected = samples.group_by("bro_id").len().sort("len", "bro_id")["bro_id"][-1]
    section_view = CrossSections(
        voxels=_corners.drop("domain").rows(),
        cell=cell_size,
        units=[{"code": _u, "name": _u, "color": "#cccccc"} for _u in _units],
        lithologies=[{"name": ZONE_LABELS[_zone], "color": SOIL_BEHAVIOR_COLORS[_zone]} for _zone in _zones],
        cpts=_cpts.to_dicts(),
        domains=[{"name": _d, "color": _c} for _d, _c in DOMAIN_COLORS.items()],
        domain_of=_corners["domain"].to_list(),
        x=_start[0],
        y=_start[1],
        z=min(_levels, key=lambda _z: abs(_z - samples["z"].median())),
        selected_cpt=_selected,
    )
    cross_sections = mo.ui.anywidget(section_view)
    cross_sections
    return cross_sections, section_view


@app.cell(hide_code=True, expand_output=True)
def cpt_profile(
    SAMPLE_HEIGHT,
    SOIL_BEHAVIOR_COLORS,
    ZONE_LABELS,
    alt,
    cell_size,
    cells,
    get_selected_cpt,
    ic,
    measured,
    mo,
    np,
    pl,
    zone_numbers,
    zone_probabilities,
):
    _bro_id = get_selected_cpt()
    mo.stop(_bro_id is None, mo.md("Click a CPT in the plan above."))
    _cpt = measured.filter(pl.col("bro_id") == _bro_id).with_columns(
        label=pl.col("zone").replace_strict(ZONE_LABELS, return_dtype=pl.String), top=pl.col("z") + SAMPLE_HEIGHT / 2, bottom=pl.col("z") - SAMPLE_HEIGHT / 2
    )
    mo.stop(_cpt.is_empty(), mo.md(f"{_bro_id} has no samples with both qc and fs."))
    _x, _y = _cpt["x"][0], _cpt["y"][0]
    # The column of cells the CPT lies in
    _column = cells.filter(
        ((pl.col("x") - _x).abs() <= cell_size["x"] / 2) & ((pl.col("y") - _y).abs() <= cell_size["y"] / 2)
    ).sort("z")
    _index = _column["cell"].to_numpy()
    _z = _column["z"].to_numpy()
    _y_scale = alt.Scale(domain=[float(min(_z.min(), _cpt["z"].min())) - 0.5, float(max(_z.max(), _cpt["z"].max())) + 0.5])
    _y_axis = alt.Y("z:Q", title="z (m NAP)", scale=_y_scale)
    _band = _column.select("z").with_columns(*(pl.Series(_p, ic[_p][_index]) for _p in ("p10", "p50", "p90")))
    _zone_scale = alt.Scale(domain=list(ZONE_LABELS.values()), range=[SOIL_BEHAVIOR_COLORS[_z] for _z in ZONE_LABELS])
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
        .encode(x=alt.X("p10:Q", title="Ic", scale=alt.Scale(domain=[1, 4.5])), x2="p90:Q", y=_y_axis)
    )
    _median = alt.Chart(_band).mark_line(color="#1f3b63", strokeWidth=2).encode(x="p50:Q", y=_y_axis, order="z:Q")
    _points = (
        alt.Chart(_cpt.select("z", "label", value=pl.col("ic")))
        .mark_circle(color="black", size=18)
        .encode(x=_ic_axis, y=_y_axis, tooltip=["z", "label", alt.Tooltip("value:Q", format=".2f")])
    )
    # The probability of each zone per cell, stacked from zone 1 up
    _stacked = np.cumsum(zone_probabilities[:, _index], axis=0)
    _bars = pl.concat(
        [
            pl.DataFrame(
                {
                    "z": _z,
                    "top": _z + cell_size["z"] / 2,
                    "bottom": _z - cell_size["z"] / 2,
                    "start": _stacked[_k] - zone_probabilities[_k, _index],
                    "end": _stacked[_k],
                    "probability": zone_probabilities[_k, _index],
                    "label": ZONE_LABELS[int(_zone)],
                }
            )
            for _k, _zone in enumerate(zone_numbers)
        ]
    ).filter(pl.col("probability") > 0)
    _probabilities = (
        alt.Chart(_bars)
        .mark_rect()
        .encode(
            x=alt.X("start:Q", title="Probability of each SBTn zone", scale=alt.Scale(domain=[0, 1])),
            x2="end:Q",
            y=alt.Y("top:Q", title=None, scale=_y_scale),
            y2="bottom:Q",
            color=alt.Color("label:N", title="SBTn zone", scale=_zone_scale, legend=alt.Legend(labelLimit=220)),
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
            mo.md(
                f"{_bro_id} at x = {_x:.0f}, y = {_y:.0f}, in the column of cells of "
                f"{cell_size['x']:g} × {cell_size['y']:g} m around it: Ic of the realizations from P10 to P90 with their "
                "median and the CPT samples as dots, the probabilities of the zones, and the zones of the CPT samples."
            ),
            alt.hconcat(
                (_rules + _area + _median + _points).properties(width=280, height=440),
                _probabilities.properties(width=240, height=440),
                _measured,
            ).resolve_scale(y="shared"),
        ]
    )
    return


@app.cell(hide_code=True)
def section_values(
    ZONE_LABELS,
    color_by,
    ic,
    most_likely_probability,
    np,
    probability_of,
    section_view,
    zone_numbers,
    zone_probabilities,
):
    # The cross-sections colored by what color_by shows. Colored by a class, the value under the pointer is
    # the probability of the most likely zone.
    _values, _label, _low, _high, _scheme = most_likely_probability, "Probability of the most likely SBTn zone", 0.0, 1.0, "viridis"
    if color_by.value == "probability":
        _index = int(np.searchsorted(zone_numbers, probability_of.value))
        _values, _label = zone_probabilities[_index], f"Probability of {ZONE_LABELS[probability_of.value]}"
    elif color_by.value == "ic median":
        _values, _label, _low, _high = ic["p50"], "Ic median", 1.31, 3.6
    elif color_by.value == "ic spread":
        _values = ic["p90"] - ic["p10"]
        _label, _low, _high, _scheme = "Ic P90 − P10", 0.0, float(np.nanpercentile(_values, 98)), "oranges"
    section_view.values = np.asarray(_values, dtype=np.float32).tobytes()
    section_view.value_scale = {"label": _label, "log": False, "min": _low, "max": _high, "scheme": _scheme}
    section_view.color_by = {"most likely": "lithology", "domain": "domain"}.get(color_by.value, "value")
    return


@app.cell(hide_code=True)
def selected_cpt(mo):
    # The CPT clicked in the cross-sections
    get_selected_cpt, set_selected_cpt = mo.state(None)
    return get_selected_cpt, set_selected_cpt


@app.cell(hide_code=True)
def follow_selected_cpt(cross_sections, get_selected_cpt, set_selected_cpt):
    # cross_sections also changes when the sections move; only another CPT goes on to what shows it
    if cross_sections.selected_cpt != get_selected_cpt():
        set_selected_cpt(cross_sections.selected_cpt)
    return


@app.cell(hide_code=True)
def check_intro(mo):
    mo.md(r"""
    ## 3 · Checks

    The CPT samples are classified the same way as the cells, with GeoTOP's ground: the zones of the
    cells should follow theirs. The first chart compares the shares of the zones per domain: of the CPT
    samples, of all realizations, and of the most likely zone, which leans towards the zones that are common
    in the domain. The table asks the same of the cells the CPT samples lie in. Since the realizations are
    conditioned on those samples, it shows that the classification keeps what the simulation honors, not how
    well it predicts the soil behavior type away from the CPTs.
    """)
    return


@app.cell(hide_code=True)
def measured(
    GAMMA_MISSING,
    SAMPLE_HEIGHT,
    VOXEL,
    ground_levels,
    np,
    pl,
    robertson,
    samples,
    voxels,
):
    def classified_samples(samples, height):
        """CPT samples of a height with a qc and fs, with their zone and Ic, on all levels of their height in GeoTOP's
        voxels so that what lies above them weighs as above the cells"""
        _usable = samples.filter((pl.col("qc") > 0) & (pl.col("fs") > 0)).join(
            ground_levels, left_on=["column_x", "column_y"], right_on=["x", "y"]
        )
        _ids = _usable["bro_id"].unique().sort().to_list()
        _offsets = -VOXEL / 2 + (np.arange(round(VOXEL / height)) + 0.5) * height
        _levels = np.unique(np.round(voxels["z"].unique().to_numpy()[:, None] + _offsets, 3))[::-1]
        _rows = _usable["bro_id"].replace_strict({_b: _i for _i, _b in enumerate(_ids)}, return_dtype=pl.Int64).to_numpy()
        _depths = np.searchsorted(-_levels, -_usable["z"].to_numpy())
        _qc, _fs = np.full((2, len(_ids), len(_levels)), np.nan)
        _qc[_rows, _depths] = _usable["qc"].to_numpy()
        _fs[_rows, _depths] = _usable["fs"].to_numpy()
        _ground = _usable.group_by("bro_id").agg(pl.first("ground_level")).sort("bro_id")["ground_level"].to_numpy()
        _result = robertson(_qc, _fs, _levels, _ground, gamma_missing=GAMMA_MISSING)
        return _usable.select("bro_id", "x", "y", "z", "voxel_z", "domain").with_columns(
            pl.Series("zone", _result["zone"][_rows, _depths], dtype=pl.Int64),
            pl.Series("ic", _result["ic"][_rows, _depths]),
        )


    measured = classified_samples(samples, SAMPLE_HEIGHT)
    return classified_samples, measured


@app.cell(hide_code=True)
def zone_shares(
    DOMAIN_COLORS,
    SOIL_BEHAVIOR_COLORS,
    ZONE_LABELS,
    alt,
    cells,
    measured,
    most_likely,
    pl,
    zone_numbers,
    zone_probabilities,
):
    def _shares(source, frame):
        return frame.select(
            pl.lit(source).alias("source"), "domain", "zone", "share"
        )

    _samples = (
        measured.group_by("domain", "zone")
        .len()
        .with_columns(share=pl.col("len") / pl.col("len").sum().over("domain"))
    )
    _likely = (
        cells.select("domain")
        .with_columns(zone=pl.Series(most_likely, dtype=pl.Int64))
        .group_by("domain", "zone")
        .len()
        .with_columns(share=pl.col("len") / pl.col("len").sum().over("domain"))
    )
    _realizations = pl.concat(
        [
            cells.select("domain")
            .with_columns(share=pl.Series(_probabilities, dtype=pl.Float64))
            .group_by("domain")
            .agg(pl.mean("share"))
            .with_columns(zone=pl.lit(int(_zone), dtype=pl.Int64))
            for _zone, _probabilities in zip(zone_numbers, zone_probabilities)
        ]
    )
    _order = ["CPT samples", "All realizations", "Most likely zone"]
    _frame = pl.concat(
        [
            _shares(_order[0], _samples),
            _shares(_order[1], _realizations),
            _shares(_order[2], _likely),
        ],
        how="vertical_relaxed",
    ).with_columns(
        label=pl.col("zone").replace_strict(
            ZONE_LABELS, return_dtype=pl.String
        )
    )
    alt.Chart(_frame.filter(pl.col("share") > 0)).mark_bar().encode(
        x=alt.X(
            "share:Q",
            title="Share of the domain",
            stack="normalize",
            axis=alt.Axis(format="%"),
        ),
        y=alt.Y("source:N", title=None, sort=_order),
        color=alt.Color(
            "label:N",
            title="SBTn zone",
            scale=alt.Scale(
                domain=list(ZONE_LABELS.values()),
                range=[SOIL_BEHAVIOR_COLORS[_z] for _z in ZONE_LABELS],
            ),
            legend=alt.Legend(labelLimit=220),
        ),
        order=alt.Order("zone:Q"),
        row=alt.Row(
            "domain:N",
            title=None,
            sort=list(DOMAIN_COLORS),
            header=alt.Header(labelAngle=0, labelAlign="left"),
        ),
        tooltip=[
            "domain",
            "source",
            "label",
            alt.Tooltip("share:Q", format=".1%"),
        ],
    ).properties(width=400, height=54)
    return


@app.cell(hide_code=True)
def at_the_cpts(
    DOMAIN_COLORS,
    cell_size,
    cells,
    measured,
    mo,
    most_likely,
    pl,
    zone_probabilities,
):
    # Each CPT sample with the cell at its center, of the same height
    _at = measured.with_columns(
        x=((pl.col("x") / cell_size["x"]).floor() + 0.5) * cell_size["x"],
        y=((pl.col("y") / cell_size["y"]).floor() + 0.5) * cell_size["y"],
        z=pl.col("z").round(3),
    ).join(cells.select("cell", "x", "y", pl.col("z").round(3)), on=["x", "y", "z"])
    _index = _at["cell"].to_numpy()
    _at = _at.with_columns(
        same=pl.Series(most_likely[_index] == _at["zone"].to_numpy()),
        probability=pl.Series(zone_probabilities[_at["zone"].to_numpy() - 1, _index]),
    )


    def _row(domain, frame):
        return {
            "domain": domain,
            "CPT samples": frame.height,
            "their zone is the most likely (%)": round(100 * frame["same"].mean(), 1),
            "mean probability of their zone (%)": round(100 * frame["probability"].mean(), 1),
        }


    mo.ui.table(
        pl.DataFrame(
            [_row(_domain, _at.filter(pl.col("domain") == _domain)) for _domain in DOMAIN_COLORS] + [_row("all", _at)]
        ),
        selection=None,
        pagination=False,
        style_cell=lambda _row, column, value: {"backgroundColor": DOMAIN_COLORS.get(value, "#ffffff")} if column == "domain" else {},
    )
    return


@app.cell(hide_code=True)
def geotop_intro(mo):
    mo.md(r"""
    The chart below compares the most likely zone with GeoTOP's lithology class of the voxel a cell lies in: per
    class, the share of its cells in each zone. They answer different questions: GeoTOP's classes describe
    what the soil is made of, Robertson's zones how it behaves under the cone. The chart shows where they
    differ, not which is right.
    """)
    return


@app.cell(hide_code=True)
def geotop_comparison(ZONE_LABELS, alt, cells, most_likely, pl):
    _frame = (
        cells.select("grondsoort")
        .with_columns(zone=pl.Series(most_likely, dtype=pl.Int64))
        .group_by("grondsoort", "zone")
        .len()
        .with_columns(share=pl.col("len") / pl.col("len").sum().over("grondsoort"))
        .with_columns(label=pl.col("zone").replace_strict(ZONE_LABELS, return_dtype=pl.String))
    )
    _classes = cells.group_by("grondsoort").len().sort("len", descending=True)["grondsoort"].to_list()
    _x = alt.X("label:N", title="Most likely zone", sort=list(ZONE_LABELS.values()), axis=alt.Axis(labelAngle=-40))
    _y = alt.Y("grondsoort:N", title="GeoTOP lithology class", sort=_classes)
    _base = alt.Chart(_frame).encode(x=_x, y=_y)
    (
        _base.mark_rect().encode(
            color=alt.Color("share:Q", title="Share of the class", scale=alt.Scale(scheme="blues", domain=[0, 1]), legend=alt.Legend(format="%")),
            tooltip=["grondsoort", "label", "len", alt.Tooltip("share:Q", format=".1%")],
        )
        + _base.mark_text(fontSize=11).encode(
            text=alt.Text("share:Q", format=".0%"),
            color=alt.condition("datum.share > 0.5", alt.value("white"), alt.value("#333333")),
        )
    ).properties(width=480, height=220)
    return


if __name__ == "__main__":
    app.run()
