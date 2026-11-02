# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair",
#     "anywidget==0.11.0",
#     "gstools==1.7.0",
#     "h5netcdf==1.8.2",
#     "h5py==3.16.0",
#     "marimo>=0.25.2",
#     "marimo-lens==0.2.4",
#     "numpy",
#     "polars==2.1.0",
#     "pyarrow",
#     "scipy==1.18.1",
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
    # Simulation

    Conditional Gaussian simulation of CPT parameters in each simulation domain: many equally likely
    realizations of qc, fs or Rf in the domain's voxels, each honoring the CPTs and the domain's variogram.
    Their spread is the uncertainty between the CPTs.

    Reads the simulation domains that `02_simulation_domains.py` saves (`notebooks/simulation_domains.json`,
    `data/voxel_domains.parquet` and `data/sample_domains.parquet`) and the variograms that
    `03_variograms.py` saves (`notebooks/variograms.json`). Per domain, the CPT samples are transformed and
    detrended as in `03` and turned into normal scores, the scores are simulated with the domain's
    variogram, conditioned on the CPTs by simple kriging, and the simulated scores are transformed back
    through the domain's distribution of the CPT values, with the trend added again.
    """)
    return


@app.cell
def _():
    import hashlib
    import json
    from datetime import datetime
    from pathlib import Path
    from statistics import NormalDist

    import altair as alt
    import anywidget
    import gstools as gs
    import marimo as mo
    import numpy as np
    import polars as pl
    import traitlets
    import xarray as xr
    from marimo_lens import Lens
    from scipy.linalg import pinvh
    from scipy.spatial.distance import cdist

    # The charts take tens of thousands of simulated cells
    alt.data_transformers.disable_max_rows()
    return (
        Lens,
        NormalDist,
        Path,
        alt,
        anywidget,
        cdist,
        datetime,
        gs,
        hashlib,
        json,
        mo,
        np,
        pinvh,
        pl,
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
    # What 02_simulation_domains.py and 03_variograms.py save; the cells that read them run again when they
    # are saved. The simulation runs are saved in SIMULATIONS_DIR.
    DOMAINS_JSON = Path(mo.notebook_dir()) / "simulation_domains.json"
    VARIOGRAMS_JSON = Path(mo.notebook_dir()) / "variograms.json"
    SIMULATIONS_DIR = DATA_DIR / "simulations"
    domains_json = mo.watch.file(DOMAINS_JSON)
    variograms_json = mo.watch.file(VARIOGRAMS_JSON)
    voxels_parquet = mo.watch.file(DATA_DIR / "voxel_domains.parquet")
    samples_parquet = mo.watch.file(DATA_DIR / "sample_domains.parquet")
    return (
        SIMULATIONS_DIR,
        domains_json,
        samples_parquet,
        variograms_json,
        voxels_parquet,
    )


@app.cell(hide_code=True)
def read_inputs(
    Path,
    domains_json,
    json,
    mo,
    pl,
    samples_parquet,
    variograms_json,
    voxels_parquet,
):
    mo.stop(
        not all(Path(_f).exists() for _f in (domains_json, voxels_parquet, samples_parquet)),
        mo.md("Save the simulation domains in `02_simulation_domains.py` first."),
    )
    mo.stop(not Path(variograms_json).exists(), mo.md("Save the variograms in `03_variograms.py` first."))
    domain_definition = json.loads(Path(domains_json).read_text(encoding="utf-8"))
    saved_variograms = json.loads(Path(variograms_json).read_text(encoding="utf-8"))
    # Each parameter's variograms carry when they were saved and the date of the simulation domains they were
    # fitted on; neither changes the realizations
    SAVE_DATES = ("saved", "simulation_domains_saved")
    # The domains from the top down, in the colors 02 gave them
    DOMAIN_COLORS = domain_definition["colors"]
    # The GeoTOP voxels in a simulation domain, and the CPT samples of 0.5 m in them
    voxels = pl.read_parquet(Path(voxels_parquet)).filter(pl.col("domain").is_not_null()).select(
        "x", "y", "z", "domain", "stratigraphic_unit", "grondsoort"
    )
    samples = pl.read_parquet(Path(samples_parquet)).filter(pl.col("domain").is_not_null())


    def _problem(definition):
        """Why a parameter's saved variograms cannot be simulated in the saved simulation domains, or None"""
        _fitted_on = definition.get("simulation_domains_saved")
        if _fitted_on != domain_definition["saved"]:
            return f"fitted on the simulation domains saved on {_fitted_on}" if _fitted_on else "fitted on unknown simulation domains"
        _missing = [_domain for _domain in DOMAIN_COLORS if _domain not in definition["domains"]]
        return f"without variograms for {', '.join(_missing)}" if _missing else None


    # The parameters 03 saved variograms of, and those of them that can be simulated: fitted on the saved
    # simulation domains, with variograms for each of them
    _problems = {_name: _problem(_value) for _name, _value in saved_variograms.items() if isinstance(_value, dict)}
    SIMULATED_PARAMETERS = [_name for _name, _reason in _problems.items() if _reason is None]
    _unusable = mo.callout(
        mo.md(
            "These variograms do not belong to the simulation domains saved in `02` on "
            f"{domain_definition['saved']}, so they cannot be simulated; save them in `03` again:\n\n"
            + "\n".join(f"- **{_name}**: {_reason}" for _name, _reason in _problems.items() if _reason)
        ),
        kind="warn",
    )
    mo.stop(
        not SIMULATED_PARAMETERS,
        _unusable if _problems else mo.md("Save the variograms of a parameter in `03_variograms.py` first."),
    )
    mo.vstack(
        [
            mo.md(
                f"**{voxels.height} GeoTOP voxels** in {len(DOMAIN_COLORS)} simulation domains, saved in `02` on "
                f"{domain_definition['saved']}, with **{samples.height} CPT samples** from "
                f"{samples['bro_id'].n_unique()} CPTs. Variograms saved in `03` of "
                + ", ".join(f"**{_name}** on {saved_variograms[_name]['saved']}" for _name in SIMULATED_PARAMETERS)
                + "."
            ),
            _unusable if len(SIMULATED_PARAMETERS) < len(_problems) else mo.md(""),
        ]
    )
    return (
        DOMAIN_COLORS,
        SAVE_DATES,
        SIMULATED_PARAMETERS,
        domain_definition,
        samples,
        saved_variograms,
        voxels,
    )


@app.cell(hide_code=True)
def settings_intro(mo):
    mo.md(r"""
    ## 1 · The simulation

    The simulation cells divide each GeoTOP voxel of 100 × 100 × 0.5 m into cells of the chosen horizontal
    and vertical resolution, since the horizontal length scales of the variograms are 25–200 m and the vertical ones
    about 0.5–6 m: on whole voxels, the values of neighboring voxels would be nearly unrelated. Each
    parameter is simulated on its own, so the realizations of qc and Rf are not correlated with each other
    beyond what the CPTs impose.

    Simulate saves one run with the chosen parameters, unless the same run was saved before (see section
    4). The table below the form lists the saved runs, the latest first; the selected run is shown in the
    cross-sections and checks below. After Simulate, its run is selected.
    """)
    return


@app.cell(hide_code=True)
def settings(SIMULATED_PARAMETERS, gs, mo):
    # The parameters, as 03 names them, and the covariance models of their variograms
    PARAMETERS = {"qc (cone resistance)": "qc", "fs (sleeve friction)": "fs", "Rf (friction ratio)": "rf"}
    UNITS = {"qc": "MPa", "fs": "MPa", "rf": "%"}
    MODELS = {"Exponential": gs.Exponential, "Spherical": gs.Spherical, "Gaussian": gs.Gaussian}
    # Resolutions that divide a voxel of 100 × 100 × 0.5 m
    HORIZONTAL_RESOLUTIONS = {"100 m: the GeoTOP voxels": 100.0, "50 m": 50.0, "25 m": 25.0, "20 m": 20.0, "10 m": 10.0}
    VERTICAL_RESOLUTIONS = {"0.5 m: the GeoTOP voxels": 0.5, "25 cm": 0.25, "10 cm": 0.1}
    # qc until Simulate is pressed, if its variograms can be simulated
    _default = "qc" if "qc" in SIMULATED_PARAMETERS else SIMULATED_PARAMETERS[0]
    DEFAULT_SETTINGS = {"parameters": [_default], "horizontal": 25.0, "vertical": 0.5, "realizations": 10, "seed": 2026}
    _simulated = {_label: _name for _label, _name in PARAMETERS.items() if _name in SIMULATED_PARAMETERS}
    simulation_settings = (
        mo.md("{parameters}\n\n{horizontal} &nbsp; {vertical}\n\n{realizations} &nbsp; {seed}")
        .batch(
            parameters=mo.ui.multiselect(_simulated, value=[_l for _l, _n in _simulated.items() if _n == _default], label="Parameters"),
            horizontal=mo.ui.dropdown(HORIZONTAL_RESOLUTIONS, value="25 m", label="Horizontal resolution"),
            vertical=mo.ui.dropdown(VERTICAL_RESOLUTIONS, value="0.5 m: the GeoTOP voxels", label="Vertical resolution"),
            realizations=mo.ui.slider(1, 50, value=10, show_value=True, label="Realizations"),
            seed=mo.ui.number(value=2026, label="Seed"),
        )
        .form(submit_button_label="Simulate", bordered=True)
    )
    simulation_settings
    return DEFAULT_SETTINGS, MODELS, PARAMETERS, UNITS, simulation_settings


@app.cell(hide_code=True)
def simulate(
    DOMAIN_COLORS,
    MODELS,
    PARAMETERS,
    SIMULATIONS_DIR,
    UNITS,
    cdist,
    cells,
    conditioning,
    datetime,
    grid_coords,
    grid_index,
    gs,
    json,
    mo,
    np,
    parameter_definitions,
    pinvh,
    pl,
    run_definition,
    run_path,
    saved_variograms,
    settings,
    xr,
):
    def _variogram_model(name, domain):
        """A domain's variogram of one parameter as a 3D GSTools model: anisotropic, with the horizontal length
        scale along x and y and the vertical one along z"""
        _definition = saved_variograms[name]
        _variogram = _definition["domains"][domain]
        _len_scale = _variogram["len_scale"]
        return MODELS[_variogram.get("model", _definition.get("model"))](
            dim=3,
            var=1.0 - _variogram["nugget"],
            len_scale=[
                _len_scale["horizontal"],
                _len_scale["horizontal"],
                _len_scale["vertical"],
            ],
            nugget=_variogram["nugget"],
        )

    # Coordinates from the south-west corner of the cells, so that the kriging works with small numbers
    _origin = np.array([cells["x"].min(), cells["y"].min(), 0.0])
    # The cells kriged at once: their covariances with the data take CHUNK × data samples × 8 bytes
    CHUNK = 10_000
    # Each parameter's own seeds, whichever other parameters are simulated with it
    _parameter_number = {_name: _p for _p, _name in enumerate(PARAMETERS.values())}

    def _positions(frame):
        return frame.select("x", "y", "z").to_numpy() - _origin

    def _condition(model, fields, cell_positions, data_positions, scores):
        """Unconditioned fields (realizations × cells and data samples) conditioned on the data's normal scores
        by simple kriging of the differences between the data and the fields at the data, all realizations
        at once and the cells in chunks. Distances are taken with z stretched by the anisotropy, so that the
        model's horizontal length scale holds in all directions. The nugget counts as measurement error: it
        is on the data's diagonal only."""
        _stretch = np.array([1.0, 1.0, 1.0 / model.anis[1]])
        _cells, _data = cell_positions * _stretch, data_positions * _stretch
        _data_covariance = model.covariance(
            cdist(_data, _data)
        ) + model.nugget * np.eye(len(_data))
        # The kriging of the differences as weights of the data's covariances: data samples × realizations
        _weights = pinvh(_data_covariance) @ (
            scores[:, None] - fields[:, len(_cells) :].T
        )
        _conditioned = fields[:, : len(_cells)].copy()
        for _start in range(0, len(_cells), CHUNK):
            _chunk = slice(_start, _start + CHUNK)
            _conditioned[:, _chunk] += (
                model.covariance(cdist(_cells[_chunk], _data)) @ _weights
            ).T
        return _conditioned

    def _simulate(name):
        """A parameter's realizations as an array of realizations × cells. Per domain: unconditioned fields of
        normal scores with its variogram (GSTools' randomization method), conditioned on its CPT samples by
        simple kriging with mean 0; the scores transformed back through its CPT values' distribution (beyond
        the lowest and highest CPT value, the lowest and highest), the trend added, and 10 raised to it for
        log10 parameters."""
        _definition = saved_variograms[name]
        _simulated = np.full((settings["realizations"], cells.height), np.nan)
        for _d, _domain in enumerate(DOMAIN_COLORS):
            _data = conditioning.filter(
                (pl.col("parameter") == name)
                & (pl.col("domain") == _domain)
            ).sort("score")
            _cells = cells.filter(pl.col("domain") == _domain)
            _model = _variogram_model(name, _domain)
            _cell_positions, _data_positions = (
                _positions(_cells),
                _positions(_data),
            )
            _all_positions = np.vstack(
                [_cell_positions, _data_positions]
            ).T
            _fields = np.stack(
                [
                    gs.SRF(
                        _model,
                        seed=settings["seed"] + 1000 * _r + 10 * _d + _parameter_number[name],
                    )(_all_positions, store=False)
                    for _r in range(settings["realizations"])
                ]
            )
            _scores = _condition(
                _model,
                _fields,
                _cell_positions,
                _data_positions,
                _data["score"].to_numpy(),
            )
            _trend = _definition["domains"][_domain]["trend"]
            _trend = (
                _trend["intercept"]
                + _trend["slope"] * _cells["z"].to_numpy()
            )
            _value = (
                np.interp(
                    _scores,
                    _data["score"].to_numpy(),
                    _data["residual"].to_numpy(),
                )
                + _trend
            )
            _simulated[:, _cells["cell"].to_numpy()] = (
                10**_value
                if _definition["transform"] == "log10"
                else _value
            )
            _bar.update()
        return _simulated

    def _cube(simulated):
        """Realizations × cells as realizations × z × y × x on the regular grid, NaN outside the simulation
        domains"""
        _shape = tuple(len(grid_coords[_axis]) for _axis in ("z", "y", "x"))
        _cube = np.full((settings["realizations"], *_shape), np.nan, dtype=np.float32)
        _cube[:, grid_index["z"], grid_index["y"], grid_index["x"]] = simulated
        return _cube

    def _saved_parameters():
        """The parameters of the runs saved before, by their definition (as sorted JSON): the file holding them"""
        _saved = {}
        for _path in SIMULATIONS_DIR.glob("*.nc"):
            with xr.open_dataset(_path, engine="h5netcdf") as _dataset:
                for _name in json.loads(_dataset.attrs["definition"])["parameters"]:
                    _saved[_dataset[_name].attrs["definition"]] = _path
        return _saved

    def _save(cubes, seconds):
        """The run as NetCDF on the regular grid: each parameter per realization, z, y and x with its
        definition and its P10, P50 and P90 per z, y and x, each cell's domain, and the run's definition. Written to a temporary file first, so that
        an interrupted save leaves no run behind."""
        _shape = tuple(len(grid_coords[_axis]) for _axis in ("z", "y", "x"))
        _domains = np.full(_shape, -1, dtype=np.int8)
        _domains[grid_index["z"], grid_index["y"], grid_index["x"]] = (
            cells["domain"].replace_strict({_d: _i for _i, _d in enumerate(DOMAIN_COLORS)}, return_dtype=pl.Int8).to_numpy()
        )
        _variables = {
            _name: (
                ("realization", "z", "y", "x"),
                _cube,
                {"units": UNITS[_name], "definition": json.dumps(parameter_definitions[_name], sort_keys=True, ensure_ascii=False)},
            )
            for _name, _cube in cubes.items()
        }
        # Each parameter's P10, P50 and P90 of the realizations per grid cell, so that what reads a run for
        # its summary need not read the realizations
        _inside = _domains >= 0
        for _name, _cube in cubes.items():
            _percentiles = np.full((3, *_shape), np.nan, dtype=np.float32)
            _percentiles[:, _inside] = np.percentile(_cube[:, _inside], [10, 50, 90], axis=0)
            for _p, _values in zip(("p10", "p50", "p90"), _percentiles):
                _variables[f"{_name}_{_p}"] = (
                    ("z", "y", "x"),
                    _values,
                    {"units": UNITS[_name], "description": f"P{_p[1:]} of the realizations of {_name}"},
                )
        _dataset = xr.Dataset(
            {
                **_variables,
                "domain": (("z", "y", "x"), _domains, {"flag_values": list(range(len(DOMAIN_COLORS))), "flag_meanings": " ".join(DOMAIN_COLORS), "missing_value": -1}),
            },
            coords={"realization": np.arange(1, settings["realizations"] + 1), **grid_coords},
            attrs={
                "definition": json.dumps(run_definition, ensure_ascii=False),
                "crs": "EPSG:28992 (RD New), z in m NAP",
                "created": datetime.now().isoformat(timespec="seconds"),
                "seconds": round(seconds, 1),
            },
        )
        run_path.parent.mkdir(parents=True, exist_ok=True)
        _temporary = run_path.with_suffix(".nc.tmp")
        _dataset.to_netcdf(
            _temporary,
            engine="h5netcdf",
            encoding={
                _name: {"zlib": True, "complevel": 4, **({"chunksizes": (1, *_shape)} if _name in cubes else {})}
                for _name in _variables
            },
        )
        _temporary.replace(run_path)

    # The run of the last Simulate: read when it was saved before; otherwise each parameter copied from a run
    # saved before with the same parameter definition, or simulated, and the run saved as soon as it is done
    _report = []
    if run_path.exists():
        _report.append(f"This run was saved before, as `{run_path.name}`.")
    else:
        _saved = _saved_parameters()
        _keys = {_name: json.dumps(_definition, sort_keys=True, ensure_ascii=False) for _name, _definition in parameter_definitions.items()}
        _cubes, _seconds = {}, 0.0
        with mo.status.progress_bar(
            total=max(sum(_key not in _saved for _key in _keys.values()) * len(DOMAIN_COLORS), 1),
            title="Simulating",
            show_eta=True,
        ) as _bar:
            for _name, _key in _keys.items():
                if _key in _saved:
                    with xr.open_dataset(_saved[_key], engine="h5netcdf") as _dataset:
                        _cubes[_name] = _dataset[_name].values
                    _report.append(f"Copied {_name} from `{_saved[_key].name}`, simulated before with the same inputs.")
                else:
                    _started = datetime.now()
                    _cubes[_name] = _cube(_simulate(_name))
                    _seconds += (datetime.now() - _started).total_seconds()
                    _report.append(f"Simulated {_name} in {(datetime.now() - _started).total_seconds():.0f} s.")
        _save(_cubes, _seconds)
        _report.append(f"Saved the run as `{run_path.name}`.")
    # The run the table selects, and what was done for it, shown under the Simulate form
    latest_run = run_path
    simulation_report = " ".join(_report)
    mo.md(simulation_report)
    return (latest_run,)


@app.cell(hide_code=True)
def saved_runs(
    SAVE_DATES,
    SIMULATIONS_DIR,
    domain_definition,
    json,
    latest_run,
    mo,
    pl,
    saved_variograms,
    xr,
):
    # The runs saved in SIMULATIONS_DIR, the latest first, with the run of the last Simulate selected. A run
    # has current inputs when its variograms and simulation domains are the ones saved now.
    _domains_now = {_k: _v for _k, _v in domain_definition.items() if _k != "saved"}


    def _current(definition):
        return definition["simulation_domains"] == _domains_now and all(
            _variograms == {_k: _v for _k, _v in saved_variograms.get(_name, {}).items() if _k not in SAVE_DATES}
            for _name, _variograms in definition["variograms"].items()
        )


    _rows = []
    for _path in SIMULATIONS_DIR.glob("*.nc"):
        with xr.open_dataset(_path, engine="h5netcdf") as _dataset:
            _definition = json.loads(_dataset.attrs["definition"])
            _rows.append(
                {
                    "parameters": ", ".join(_definition["parameters"]),
                    "horizontal (m)": _definition["resolution"]["horizontal"],
                    "vertical (m)": _definition["resolution"]["vertical"],
                    "realizations": _definition["realizations"],
                    "seed": _definition["seed"],
                    "current inputs": _current(_definition),
                    "created": _dataset.attrs["created"],
                    "minutes simulating": round(_dataset.attrs["seconds"] / 60, 1),
                    "MB": round(_path.stat().st_size / 1e6, 1),
                    "file": _path.name,
                }
            )
    _runs = pl.DataFrame(_rows).sort("created", descending=True)
    saved_runs = mo.ui.table(
        _runs,
        selection="single",
        initial_selection=[_runs["file"].to_list().index(latest_run.name)],
        page_size=10,
        label="Saved runs",
    )
    saved_runs
    return (saved_runs,)


@app.cell(hide_code=True)
def selected_run(SIMULATIONS_DIR, json, mo, np, pl, saved_runs, voxels, xr):
    mo.stop(saved_runs.value.is_empty(), mo.md("Select a run in the table above."))
    # The selected run: its definition, its cells (where the grid has a domain) and per parameter its
    # realizations as realizations × cells and their statistics per cell
    with xr.open_dataset(SIMULATIONS_DIR / saved_runs.value["file"][0], engine="h5netcdf") as _dataset:
        run = json.loads(_dataset.attrs["definition"])
        # The domain index of each grid cell; xarray reads its missing value, -1, as NaN
        _domains = _dataset["domain"].fillna(-1).values.astype(int)
        _names = np.array(_dataset["domain"].attrs["flag_meanings"].split())
        _iz, _iy, _ix = np.nonzero(_domains >= 0)
        simulated = {_name: _dataset[_name].values[:, _iz, _iy, _ix] for _name in run["parameters"]}
        # Per parameter, the P10, P50 and P90 of its realizations per cell, saved with the run
        statistics = {
            _name: {_p: _dataset[f"{_name}_{_p}"].values[_iz, _iy, _ix] for _p in ("p10", "p50", "p90")}
            for _name in run["parameters"]
        }
        _coords = {_axis: _dataset[_axis].values for _axis in ("x", "y", "z")}
    # Whether each parameter was simulated as its log10
    run_log = {_name: _variograms["transform"] == "log10" for _name, _variograms in run["variograms"].items()}
    # Each cell with the stratigraphic unit and lithology class of the GeoTOP voxel it lies in (a voxel's x
    # and y are its south-west corner, its z its center)
    run_cells = (
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
        .drop("voxel_x", "voxel_y", "voxel_z")
        .with_columns(pl.col("stratigraphic_unit", "grondsoort").fill_null("unknown"))
    )
    return run, run_cells, run_log, simulated, statistics


@app.cell(hide_code=True)
def view_intro(mo):
    mo.md(r"""
    ## 2 · The realizations

    The selected run's cells from above at one level, with a west–east section above and a south–north section to the
    right, as in `02`: drag the red dot in the plan to move the sections, and drag in either section to
    change the plan's level. Color the cells by one realization or a statistic of all realizations per cell
    (the median, P10, P90 or their spread), or by their simulation domain. In the sections, each GeoTOP
    column the CPTs cross shows the median qc of its CPTs, in a band from their 10th to their 90th
    percentile; hover over a CPT in the plan for its own qc, and over a cell for its value.
    """)
    return


@app.cell(hide_code=True)
def view_controls(PARAMETERS, mo, run, simulated):
    # What the cross-sections show of the selected run
    _labels = {_name: _label for _label, _name in PARAMETERS.items()}
    view_controls = mo.ui.dictionary(
        {
            "parameter": mo.ui.dropdown({_labels[_n]: _n for _n in simulated}, value=_labels[next(iter(simulated))], label="Parameter"),
            "shown": mo.ui.dropdown(
                {"Median (P50)": "p50", "P10": "p10", "P90": "p90", "Spread (P90 against P10)": "spread"}
                | {f"Realization {_r + 1}": f"r{_r}" for _r in range(run["realizations"])},
                value="Median (P50)",
                label="Show",
            ),
        }
    )
    mo.hstack([view_controls["parameter"], view_controls["shown"]], justify="start", gap=2)
    return (view_controls,)


@app.cell(hide_code=True)
def cross_sections_widget(Path, anywidget, mo, traitlets):
    class CrossSections(anywidget.AnyWidget):
        """The cells from above at the level z, with a west–east section through the row of cells at y and a
        south–north one through the column of cells at x (x and y a cell's south-west corner)"""

        _esm = Path(mo.notebook_dir()) / "cross_sections.js"
        # Per cell: x, y, z and its indices in units and lithologies, which hold each stratigraphic unit's
        # code, name and color and each lithology class's name and color; the cells' size along x, y and z
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
        # What the cells can be colored by, and are: "value" or "domain"
        color_modes = traitlets.List(["value", "domain"]).tag(sync=True)
        color_by = traitlets.Unicode("value").tag(sync=True)
        x = traitlets.Float().tag(sync=True)
        y = traitlets.Float().tag(sync=True)
        z = traitlets.Float().tag(sync=True)

    return (CrossSections,)


@app.cell(hide_code=True, expand_output=True)
def cross_sections(CrossSections, DOMAIN_COLORS, pl, run, run_cells, samples):
    # Made once per selected run; section_values colors it. The stratigraphic units from the top down and the
    # lithology classes alphabetically, for the cell under the pointer; their colors are not shown.
    _units = run_cells.group_by("stratigraphic_unit").agg(pl.max("z")).sort("z", descending=True)["stratigraphic_unit"].to_list()
    _lithologies = run_cells["grondsoort"].unique().sort().to_list()
    _cpts = samples.sort("z", descending=True).group_by("bro_id", maintain_order=True).agg(pl.first("x", "y"), "z", "qc")
    _size = {"x": run["resolution"]["horizontal"], "y": run["resolution"]["horizontal"], "z": run["resolution"]["vertical"]}
    _corners = run_cells.select(
        (pl.col("x") - _size["x"] / 2).round(3),
        (pl.col("y") - _size["y"] / 2).round(3),
        "z",
        pl.col("stratigraphic_unit").replace_strict({_u: _i for _i, _u in enumerate(_units)}, return_dtype=pl.Int64),
        pl.col("grondsoort").replace_strict({_l: _i for _i, _l in enumerate(_lithologies)}, return_dtype=pl.Int64),
        pl.col("domain").replace_strict({_d: _i for _i, _d in enumerate(DOMAIN_COLORS)}, default=-1, return_dtype=pl.Int64),
    )
    # The sections start through the cell with the most CPTs, at the CPT samples' median level
    _origin = {_axis: _corners[_axis].min() for _axis in ("x", "y")}
    _start = (
        samples.select(
            *((_origin[_a] + ((pl.col(_a) - _origin[_a]) // _size[_a]) * _size[_a]).round(3).alias(_a) for _a in ("x", "y")),
            "bro_id",
        )
        .group_by("x", "y")
        .agg(pl.n_unique("bro_id"))
        .sort("bro_id", descending=True)
        .row(0)
    )
    _levels = run_cells["z"].unique().to_list()
    section_view = CrossSections(
        voxels=_corners.drop("domain").rows(),
        cell=_size,
        units=[{"code": _u, "name": _u, "color": "#cccccc"} for _u in _units],
        lithologies=[{"name": _l, "color": "#cccccc"} for _l in _lithologies],
        cpts=_cpts.to_dicts(),
        domains=[{"name": _d, "color": _c} for _d, _c in DOMAIN_COLORS.items()],
        domain_of=_corners["domain"].to_list(),
        x=_start[0],
        y=_start[1],
        z=min(_levels, key=lambda _z: abs(_z - samples["z"].median())),
    )
    section_view
    return (section_view,)


@app.cell(hide_code=True)
def section_values(
    UNITS,
    np,
    run_log,
    section_view,
    simulated,
    statistics,
    view_controls,
):
    # The cross-sections colored by what view_controls shows: a realization, a statistic or the spread
    # (P90 / P10 for log10 parameters, P90 − P10 otherwise), on a color scale over its 2nd to 98th percentile,
    # logarithmic for log10 parameters and the spread of them
    _name, _shown = view_controls.value["parameter"], view_controls.value["shown"]
    _log = run_log[_name]
    if _shown.startswith("r"):
        _values, _label = simulated[_name][int(_shown[1:])], f"{_name} realization {int(_shown[1:]) + 1} ({UNITS[_name]})"
    elif _shown == "spread":
        _p10, _p90 = statistics[_name]["p10"], statistics[_name]["p90"]
        _values, _label = (_p90 / _p10, f"{_name} P90 / P10") if _log else (_p90 - _p10, f"{_name} P90 − P10 ({UNITS[_name]})")
    else:
        _values, _label = statistics[_name][_shown], f"{_name} {_shown.upper()} ({UNITS[_name]})"
    _low, _high = np.nanpercentile(_values, [2, 98])
    section_view.values = np.asarray(_values, dtype=np.float32).tobytes()
    section_view.value_scale = {
        "label": _label,
        "log": bool(_log),
        "min": float(_low),
        "max": float(_high),
        "scheme": "oranges" if _shown == "spread" else "viridis",
    }
    return


@app.cell(hide_code=True)
def check_intro(mo):
    mo.md(r"""
    ## 3 · Checks

    The realizations should reproduce each domain's distribution of the CPT values, and near a CPT they
    should follow it. The table compares the percentiles of the CPT samples with those of all realizations
    per domain. The chart shows, for one CPT, the realizations in the cells it lies in: each realization a
    thin line, the median a thick one, P10 to P90 shaded, and the CPT samples as dots.
    """)
    return


@app.cell(hide_code=True)
def distribution(
    DOMAIN_COLORS,
    UNITS,
    mo,
    np,
    pl,
    run_cells,
    samples,
    simulated,
):
    def _percentiles(values):
        return dict(zip(("P10", "P50", "P90"), np.nanpercentile(values, [10, 50, 90])))


    # Per parameter and domain of the selected run, the percentiles of the CPT samples and of all realizations
    _rows = []
    for _name in simulated:
        for _domain in run_cells["domain"].unique(maintain_order=True):
            _index = run_cells.filter(pl.col("domain") == _domain)["cell"].to_numpy()
            _data = samples.filter((pl.col("domain") == _domain) & (pl.col(_name) > 0))[_name].to_numpy()
            _rows.append(
                {"parameter": _name, "domain": _domain, "unit": UNITS[_name]}
                | {f"CPTs {_k}": round(_v, 3) for _k, _v in _percentiles(_data).items()}
                | {f"realizations {_k}": round(_v, 3) for _k, _v in _percentiles(simulated[_name][:, _index]).items()}
            )
    mo.ui.table(
        pl.DataFrame(_rows),
        selection=None,
        style_cell=lambda _row, column, value: {"backgroundColor": DOMAIN_COLORS.get(value, "#cccccc")} if column == "domain" else {},
    )
    return


@app.cell(hide_code=True)
def check_cpt(mo, pl, samples):
    # The CPTs, with the cells they lie in
    _cpts = samples.group_by("bro_id").agg(pl.first("x"), pl.first("y"), pl.len().alias("samples")).sort("bro_id")
    check_cpt = mo.ui.dropdown(_cpts["bro_id"].to_list(), value=_cpts.sort("samples")["bro_id"][-1], label="CPT", searchable=True)
    check_cpt
    return (check_cpt,)


@app.cell(hide_code=True)
def cpt_check(
    UNITS,
    alt,
    check_cpt,
    mo,
    np,
    pl,
    run,
    run_cells,
    run_log,
    samples,
    simulated,
    statistics,
    view_controls,
):
    _name = view_controls.value["parameter"]
    _log = run_log[_name]
    _cpt = samples.filter(pl.col("bro_id") == check_cpt.value)
    _x, _y = _cpt["x"][0], _cpt["y"][0]
    # The column of cells the CPT lies in
    _column = run_cells.filter(
        ((pl.col("x") - _x).abs() <= run["resolution"]["horizontal"] / 2) & ((pl.col("y") - _y).abs() <= run["resolution"]["horizontal"] / 2)
    ).sort("z")
    _index = _column["cell"].to_numpy()
    _realizations = pl.DataFrame(
        {
            "z": np.tile(_column["z"].to_numpy(), run["realizations"]),
            "realization": np.repeat(np.arange(run["realizations"]) + 1, len(_index)),
            "value": simulated[_name][:, _index].ravel(),
        }
    )
    _band = _column.select("z").with_columns(
        p10=pl.Series(statistics[_name]["p10"][_index]),
        p50=pl.Series(statistics[_name]["p50"][_index]),
        p90=pl.Series(statistics[_name]["p90"][_index]),
    )
    _x_scale = alt.Scale(type="log" if _log else "linear")
    _title = f"{_name} ({UNITS[_name]})"
    _lines = (
        alt.Chart(_realizations)
        .mark_line(strokeWidth=0.6, opacity=0.5, color="#4c78a8")
        .encode(x=alt.X("value:Q", title=_title, scale=_x_scale), y=alt.Y("z:Q", title="z (m NAP)"), detail="realization:N", order="z:Q")
    )
    _area = alt.Chart(_band).mark_area(opacity=0.2, color="#4c78a8", orient="horizontal").encode(x="p10:Q", x2="p90:Q", y="z:Q")
    _median = alt.Chart(_band).mark_line(color="#1f3b63", strokeWidth=2).encode(x="p50:Q", y="z:Q", order="z:Q")
    _points = (
        alt.Chart(_cpt.filter(pl.col(_name) > 0).select("z", "domain", value=pl.col(_name)))
        .mark_circle(color="black", size=18)
        .encode(x="value:Q", y="z:Q", tooltip=["z", "domain", alt.Tooltip("value:Q", format=".3g")])
    )
    mo.vstack(
        [
            mo.md(f"{check_cpt.value} at x = {_x:.0f}, y = {_y:.0f}, in the column of cells of {run['resolution']['horizontal']:g} × {run['resolution']['horizontal']:g} m around it."),
            (_area + _lines + _median + _points).properties(width=420, height=440),
        ]
    )
    return


@app.cell(hide_code=True)
def simulation_intro(mo):
    mo.md(r"""
    ## 4 · How a run is simulated and saved

    Simulate saves one run in `data/simulations/` as soon as it is done, as NetCDF: each chosen parameter's
    realizations on the regular grid (realization × z × y × x, in RD New and m NAP, NaN outside the
    simulation domains) with their P10, P50 and P90 per cell, each cell's domain, and the run's definition: the parameters' variograms, the
    simulation domains, the resolution, the number of realizations and the seed. Its name ends in a hash of
    that definition, so pressing Simulate again with the same definition simulates nothing and selects the
    run saved before. A parameter simulated before with the same definition, in another run, is copied
    from it instead of simulated again.
    """)
    return


@app.cell
def grid(DEFAULT_SETTINGS, mo, np, pl, simulation_settings, voxels):
    # The settings of the last Simulate, or the defaults until it is pressed
    settings = simulation_settings.value or DEFAULT_SETTINGS
    mo.stop(not settings["parameters"], mo.md("Choose at least one parameter."))


    def _offsets(name, voxel_size, cell_size, start):
        """The offsets of the cell centers in a voxel from its coordinate, along one axis"""
        return pl.DataFrame({name: start + (np.arange(round(voxel_size / cell_size)) + 0.5) * cell_size})


    # The simulation cells: each voxel divided into cells of the horizontal resolution square and the vertical
    # resolution high, at the cells' centers. A voxel's x and y are its south-west corner, its z its center.
    cells = (
        voxels.rename({"x": "voxel_x", "y": "voxel_y", "z": "voxel_z"})
        .join(_offsets("dx", 100.0, settings["horizontal"], 0.0), how="cross")
        .join(_offsets("dy", 100.0, settings["horizontal"], 0.0), how="cross")
        .join(_offsets("dz", 0.5, settings["vertical"], -0.25), how="cross")
        .with_columns(
            x=pl.col("voxel_x") + pl.col("dx"), y=pl.col("voxel_y") + pl.col("dy"), z=(pl.col("voxel_z") + pl.col("dz")).round(3)
        )
        .drop("dx", "dy", "dz")
        .sort("domain", "z", "y", "x")
        .with_row_index("cell")
    )
    # The regular grid around the cells, as the saved runs hold it, and each cell's position in it
    grid_coords = {
        "x": np.round(np.arange(cells["x"].min(), cells["x"].max() + settings["horizontal"] / 2, settings["horizontal"]), 3),
        "y": np.round(np.arange(cells["y"].min(), cells["y"].max() + settings["horizontal"] / 2, settings["horizontal"]), 3),
        "z": np.unique(cells["z"].to_numpy()),
    }
    grid_index = {_axis: np.searchsorted(_coords, cells[_axis].to_numpy()) for _axis, _coords in grid_coords.items()}
    mo.md(
        f"**{cells.height} simulation cells** of {settings['horizontal']:g} × {settings['horizontal']:g} m × "
        f"{settings['vertical'] * 100:g} cm."
    )
    return cells, grid_coords, grid_index, settings


@app.cell
def conditioning(NormalDist, pl, samples, saved_variograms, settings):
    _inverse_normal = NormalDist().inv_cdf


    def _conditioning(name):
        """The CPT samples of one parameter with their normal scores per domain, as in 03: the transformed
        value without the domain's saved trend, ranked"""
        _definition = saved_variograms[name]
        _value = pl.col(name).log10() if _definition["transform"] == "log10" else pl.col(name)
        _trends = pl.DataFrame(
            [{"domain": _domain, **_variogram["trend"]} for _domain, _variogram in _definition["domains"].items()]
        )
        return (
            samples.filter(pl.col(name) > 0)
            .select("domain", "bro_id", "x", "y", "z", value=_value, parameter=pl.lit(name))
            .join(_trends, on="domain")
            .with_columns(residual=pl.col("value") - (pl.col("intercept") + pl.col("slope") * pl.col("z")))
            .with_columns(
                score=((pl.col("residual").rank("average").over("domain") - 0.5) / pl.len().over("domain")).map_elements(
                    _inverse_normal, return_dtype=pl.Float64
                )
            )
            .drop("intercept", "slope")
        )


    conditioning = pl.concat([_conditioning(_name) for _name in settings["parameters"]])
    return (conditioning,)


@app.cell
def simulation_runs(
    PARAMETERS,
    SAVE_DATES,
    SIMULATIONS_DIR,
    domain_definition,
    hashlib,
    json,
    saved_variograms,
    settings,
):
    # Raise when the simulation method changes, so that runs saved before are not reused
    SIMULATION_VERSION = 1


    def _parameter_definition(name):
        """Everything that decides a parameter's realizations: the method's version, the grid, the number of
        realizations and the seed, the parameter's saved variograms and the simulation domains"""
        return {
            "version": SIMULATION_VERSION,
            "parameter": name,
            "resolution": {"horizontal": settings["horizontal"], "vertical": settings["vertical"]},
            "realizations": settings["realizations"],
            "seed": settings["seed"],
            "variograms": {_k: _v for _k, _v in saved_variograms[name].items() if _k not in SAVE_DATES},
            "simulation_domains": {_k: _v for _k, _v in domain_definition.items() if _k != "saved"},
        }


    # The run of the chosen parameters, in PARAMETERS' order: each parameter's definition, and the run's,
    # whose hash names its file. A run with the same definition is not simulated again.
    parameter_definitions = {
        _name: _parameter_definition(_name) for _name in PARAMETERS.values() if _name in settings["parameters"]
    }
    run_definition = {
        **{_k: _v for _k, _v in next(iter(parameter_definitions.values())).items() if _k not in ("parameter", "variograms")},
        "parameters": list(parameter_definitions),
        "variograms": {_name: _definition["variograms"] for _name, _definition in parameter_definitions.items()},
    }
    _key = hashlib.sha256(json.dumps(run_definition, sort_keys=True).encode()).hexdigest()[:12]
    run_path = SIMULATIONS_DIR / f"{'-'.join(parameter_definitions)}_{_key}.nc"
    return parameter_definitions, run_definition, run_path


if __name__ == "__main__":
    app.run()
