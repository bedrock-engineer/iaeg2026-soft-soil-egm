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
    realisations of qc, fs or Rf in the domain's voxels, each honouring the CPTs and the domain's variogram.
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
    # fitted on; neither changes the realisations
    SAVE_DATES = ("saved", "simulation_domains_saved")
    # The domains from the top down, in the colours 02 gave them
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
    about 0.5–6 m: on whole voxels, the values of neighbouring voxels would be nearly unrelated. Each
    parameter is simulated on its own, so the realisations of qc and Rf are not correlated with each other
    beyond what the CPTs impose.
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
    DEFAULT_SETTINGS = {"parameters": [_default], "horizontal": 25.0, "vertical": 0.5, "realisations": 10, "seed": 2026}
    _simulated = {_label: _name for _label, _name in PARAMETERS.items() if _name in SIMULATED_PARAMETERS}
    simulation_settings = (
        mo.md("{parameters}\n\n{horizontal} &nbsp; {vertical}\n\n{realisations} &nbsp; {seed}")
        .batch(
            parameters=mo.ui.multiselect(_simulated, value=[_l for _l, _n in _simulated.items() if _n == _default], label="Parameters"),
            horizontal=mo.ui.dropdown(HORIZONTAL_RESOLUTIONS, value="25 m", label="Horizontal resolution"),
            vertical=mo.ui.dropdown(VERTICAL_RESOLUTIONS, value="0.5 m: the GeoTOP voxels", label="Vertical resolution"),
            realisations=mo.ui.slider(1, 50, value=10, show_value=True, label="Realisations"),
            seed=mo.ui.number(value=2026, label="Seed"),
        )
        .form(submit_button_label="Simulate", bordered=True)
    )
    simulation_settings
    return DEFAULT_SETTINGS, MODELS, PARAMETERS, UNITS, simulation_settings


@app.cell
def grid(DEFAULT_SETTINGS, mo, np, pl, simulation_settings, voxels):
    # The settings of the last Simulate, or the defaults until it is pressed
    settings = simulation_settings.value or DEFAULT_SETTINGS
    mo.stop(not settings["parameters"], mo.md("Choose at least one parameter."))


    def _offsets(name, voxel_size, cell_size, start):
        """The offsets of the cell centres in a voxel from its coordinate, along one axis"""
        return pl.DataFrame({name: start + (np.arange(round(voxel_size / cell_size)) + 0.5) * cell_size})


    # The simulation cells: each voxel divided into cells of the horizontal resolution square and the vertical
    # resolution high, at the cells' centres. A voxel's x and y are its south-west corner, its z its centre.
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


    def _run_definition(name):
        """Everything that decides a parameter's realisations: the method's version, the grid, the number of
        realisations and the seed, the parameter's saved variograms and the simulation domains"""
        return {
            "version": SIMULATION_VERSION,
            "parameter": name,
            "resolution": {"horizontal": settings["horizontal"], "vertical": settings["vertical"]},
            "realisations": settings["realisations"],
            "seed": settings["seed"],
            "variograms": {_k: _v for _k, _v in saved_variograms[name].items() if _k not in SAVE_DATES},
            "simulation_domains": {_k: _v for _k, _v in domain_definition.items() if _k != "saved"},
        }


    # Per parameter, its run's definition and the file it is saved in, named by a hash of the definition: a
    # run with the same definition is read from its file instead of simulated again
    simulation_runs = {}
    for _name in settings["parameters"]:
        _definition = _run_definition(_name)
        _key = hashlib.sha256(json.dumps(_definition, sort_keys=True).encode()).hexdigest()[:12]
        simulation_runs[_name] = {"definition": _definition, "path": SIMULATIONS_DIR / f"{_name}_{_key}.nc"}
    return (simulation_runs,)


@app.cell
def simulate(
    DOMAIN_COLORS,
    MODELS,
    PARAMETERS,
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
    pinvh,
    pl,
    saved_variograms,
    settings,
    simulation_runs,
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
        """Unconditioned fields (realisations × cells and data samples) conditioned on the data's normal scores
        by simple kriging of the differences between the data and the fields at the data, all realisations
        at once and the cells in chunks. Distances are taken with z stretched by the anisotropy, so that the
        model's horizontal length scale holds in all directions. The nugget counts as measurement error: it
        is on the data's diagonal only."""
        _stretch = np.array([1.0, 1.0, 1.0 / model.anis[1]])
        _cells, _data = cell_positions * _stretch, data_positions * _stretch
        _data_covariance = model.covariance(
            cdist(_data, _data)
        ) + model.nugget * np.eye(len(_data))
        # The kriging of the differences as weights of the data's covariances: data samples × realisations
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
        """A parameter's realisations as an array of realisations × cells. Per domain: unconditioned fields of
        normal scores with its variogram (GSTools' randomization method), conditioned on its CPT samples by
        simple kriging with mean 0; the scores transformed back through its CPT values' distribution (beyond
        the lowest and highest CPT value, the lowest and highest), the trend added, and 10 raised to it for
        log10 parameters."""
        _definition = saved_variograms[name]
        _simulated = np.full((settings["realisations"], cells.height), np.nan)
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
                    for _r in range(settings["realisations"])
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

    def _save(name, simulated, seconds):
        """A parameter's realisations as NetCDF on the regular grid: the parameter per realisation, z, y and x
        (NaN outside the simulation domains), each cell's domain, and the run's definition. Written to a
        temporary file first, so that an interrupted save leaves no run behind."""
        _shape = tuple(len(grid_coords[_axis]) for _axis in ("z", "y", "x"))
        _at = (grid_index["z"], grid_index["y"], grid_index["x"])
        _cube = np.full((settings["realisations"], *_shape), np.nan, dtype=np.float32)
        _cube[:, *_at] = simulated
        _domains = np.full(_shape, -1, dtype=np.int8)
        _domains[_at] = cells["domain"].replace_strict({_d: _i for _i, _d in enumerate(DOMAIN_COLORS)}, return_dtype=pl.Int8).to_numpy()
        _dataset = xr.Dataset(
            {
                name: (("realisation", "z", "y", "x"), _cube, {"units": UNITS[name]}),
                "domain": (("z", "y", "x"), _domains, {"flag_values": list(range(len(DOMAIN_COLORS))), "flag_meanings": " ".join(DOMAIN_COLORS), "missing_value": -1}),
            },
            coords={"realisation": np.arange(1, settings["realisations"] + 1), **grid_coords},
            attrs={
                "definition": json.dumps(simulation_runs[name]["definition"], ensure_ascii=False),
                "crs": "EPSG:28992 (RD New), z in m NAP",
                "created": datetime.now().isoformat(timespec="seconds"),
                "seconds": round(seconds, 1),
            },
        )
        _path = simulation_runs[name]["path"]
        _path.parent.mkdir(parents=True, exist_ok=True)
        _temporary = _path.with_suffix(".nc.tmp")
        _dataset.to_netcdf(
            _temporary, engine="h5netcdf", encoding={name: {"zlib": True, "complevel": 4, "chunksizes": (1, *_shape)}}
        )
        _temporary.replace(_path)

    # The runs that are not saved yet, each simulated and saved as soon as it is done
    _missing = [_name for _name, _run in simulation_runs.items() if not _run["path"].exists()]
    _report = []
    with mo.status.progress_bar(
        total=max(len(_missing) * len(DOMAIN_COLORS), 1),
        title="Simulating",
        show_eta=True,
    ) as _bar:
        for _name in _missing:
            _started = datetime.now()
            _simulated = _simulate(_name)
            _seconds = (datetime.now() - _started).total_seconds()
            _save(_name, _simulated, _seconds)
            _report.append(f"Simulated {_name} in {_seconds:.0f} s and saved it to `{simulation_runs[_name]['path'].name}`.")
    # The files the views read the realisations from
    simulation_files = {_name: _run["path"] for _name, _run in simulation_runs.items()}
    _report += [f"Read {_name} from `{simulation_runs[_name]['path'].name}`, saved before." for _name in simulation_runs if _name not in _missing]
    mo.md("\n\n".join(_report))
    return (simulation_files,)


@app.cell
def results(grid_index, simulation_files, xr):
    # Per parameter, the realisations read from its saved run, as an array of realisations × cells
    simulated = {}
    for _name, _path in simulation_files.items():
        with xr.open_dataset(_path, engine="h5netcdf") as _dataset:
            simulated[_name] = _dataset[_name].values[:, grid_index["z"], grid_index["y"], grid_index["x"]]
    return (simulated,)


@app.cell(hide_code=True)
def view_intro(mo):
    mo.md(r"""
    ## 2 · The realisations

    The cells from above at one level, with a west–east section above and a south–north section to the
    right, as in `02`: drag the red dot in the plan to move the sections, and drag in either section to
    change the plan's level. Colour the cells by one realisation or a statistic of all realisations per cell
    (the median, P10, P90 or their spread), or by their simulation domain. In the sections, each GeoTOP
    column the CPTs cross shows the median qc of its CPTs, in a band from their 10th to their 90th
    percentile; hover over a CPT in the plan for its own qc, and over a cell for its value.
    """)
    return


@app.cell(hide_code=True)
def statistics(PARAMETERS, mo, np, settings, simulated):
    # Per parameter, the statistics of the realisations per cell
    statistics = {
        _name: dict(zip(("p10", "p50", "p90"), np.nanpercentile(_values, [10, 50, 90], axis=0)))
        for _name, _values in simulated.items()
    }
    _labels = {_name: _label for _label, _name in PARAMETERS.items()}
    view_controls = mo.ui.dictionary(
        {
            "parameter": mo.ui.dropdown({_labels[_n]: _n for _n in simulated}, value=_labels[next(iter(simulated))], label="Parameter"),
            "shown": mo.ui.dropdown(
                {"Median (P50)": "p50", "P10": "p10", "P90": "p90", "Spread (P90 against P10)": "spread"}
                | {f"Realisation {_r + 1}": f"r{_r}" for _r in range(settings["realisations"])},
                value="Median (P50)",
                label="Show",
            ),
        }
    )
    mo.hstack([view_controls["parameter"], view_controls["shown"]], justify="start", gap=2)
    return statistics, view_controls


@app.cell(hide_code=True)
def cross_sections_widget(Path, anywidget, mo, traitlets):
    class CrossSections(anywidget.AnyWidget):
        """The cells from above at the level z, with a west–east section through the row of cells at y and a
        south–north one through the column of cells at x (x and y a cell's south-west corner)"""

        _esm = Path(mo.notebook_dir()) / "cross_sections.js"
        # Per cell: x, y, z and its indices in units and lithologies, which hold each stratigraphic unit's
        # code, name and colour and each lithology class's name and colour; the cells' size along x, y and z
        voxels = traitlets.List().tag(sync=True)
        cell = traitlets.Dict().tag(sync=True)
        units = traitlets.List().tag(sync=True)
        lithologies = traitlets.List().tag(sync=True)
        # Per CPT: its x and y, and its qc (MPa) per sample level z
        cpts = traitlets.List().tag(sync=True)
        # The domains' names and colours, and each cell's index in them
        domains = traitlets.List().tag(sync=True)
        domain_of = traitlets.List().tag(sync=True)
        # Per cell, a value as float32 bytes, on a colour scale {label, log, min, max, scheme}
        values = traitlets.Bytes().tag(sync=True)
        value_scale = traitlets.Dict().tag(sync=True)
        # What the cells can be coloured by, and are: "value" or "domain"
        color_modes = traitlets.List(["value", "domain"]).tag(sync=True)
        color_by = traitlets.Unicode("value").tag(sync=True)
        x = traitlets.Float().tag(sync=True)
        y = traitlets.Float().tag(sync=True)
        z = traitlets.Float().tag(sync=True)

    return (CrossSections,)


@app.cell(hide_code=True, expand_output=True)
def cross_sections(CrossSections, DOMAIN_COLORS, cells, pl, samples, settings):
    # Made once per simulation; section_values colours it. The stratigraphic units from the top down and the
    # lithology classes alphabetically, for the cell under the pointer; their colours are not shown.
    _units = cells.group_by("stratigraphic_unit").agg(pl.max("z")).sort("z", descending=True)["stratigraphic_unit"].to_list()
    _lithologies = cells["grondsoort"].unique().sort().to_list()
    _cpts = samples.sort("z", descending=True).group_by("bro_id", maintain_order=True).agg(pl.first("x", "y"), "z", "qc")
    _size = {"x": settings["horizontal"], "y": settings["horizontal"], "z": settings["vertical"]}
    _corners = cells.select(
        (pl.col("x") - _size["x"] / 2).round(3),
        (pl.col("y") - _size["y"] / 2).round(3),
        "z",
        pl.col("stratigraphic_unit").replace_strict({_u: _i for _i, _u in enumerate(_units)}, return_dtype=pl.Int64),
        pl.col("grondsoort").replace_strict({_l: _i for _i, _l in enumerate(_lithologies)}, return_dtype=pl.Int64),
        pl.col("domain").replace_strict({_d: _i for _i, _d in enumerate(DOMAIN_COLORS)}, return_dtype=pl.Int64),
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
    _levels = cells["z"].unique().to_list()
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
    saved_variograms,
    section_view,
    simulated,
    statistics,
    view_controls,
):
    # The cross-sections coloured by what view_controls shows: a realisation, a statistic or the spread
    # (P90 / P10 for log10 parameters, P90 − P10 otherwise), on a colour scale over its 2nd to 98th percentile,
    # logarithmic for log10 parameters and the spread of them
    _name, _shown = view_controls.value["parameter"], view_controls.value["shown"]
    _log = saved_variograms[_name]["transform"] == "log10"
    if _shown.startswith("r"):
        _values, _label = simulated[_name][int(_shown[1:])], f"{_name} realisation {int(_shown[1:]) + 1} ({UNITS[_name]})"
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

    The realisations should reproduce each domain's distribution of the CPT values, and near a CPT they
    should follow it. The table compares the percentiles of the CPT samples with those of all realisations
    per domain. The chart shows, for one CPT, the realisations in the cells it lies in: each realisation a
    thin line, the median a thick one, P10 to P90 shaded, and the CPT samples as dots.
    """)
    return


@app.cell(hide_code=True)
def distribution(
    DOMAIN_COLORS,
    UNITS,
    cells,
    conditioning,
    mo,
    np,
    pl,
    saved_variograms,
    simulated,
):
    def _percentiles(values):
        return dict(zip(("P10", "P50", "P90"), np.nanpercentile(values, [10, 50, 90])))


    _rows = []
    for _name in simulated:
        _log = saved_variograms[_name]["transform"] == "log10"
        for _domain in DOMAIN_COLORS:
            _index = cells.filter(pl.col("domain") == _domain)["cell"].to_numpy()
            _data = conditioning.filter((pl.col("parameter") == _name) & (pl.col("domain") == _domain))["value"].to_numpy()
            _cpt = _percentiles(10**_data if _log else _data)
            _sim = _percentiles(simulated[_name][:, _index])
            _rows.append(
                {"parameter": _name, "domain": _domain, "unit": UNITS[_name]}
                | {f"CPTs {_k}": round(_v, 3) for _k, _v in _cpt.items()}
                | {f"realisations {_k}": round(_v, 3) for _k, _v in _sim.items()}
            )
    mo.ui.table(
        pl.DataFrame(_rows),
        selection=None,
        style_cell=lambda _row, column, value: {"backgroundColor": DOMAIN_COLORS[value]} if column == "domain" else {},
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
    cells,
    check_cpt,
    mo,
    np,
    pl,
    samples,
    saved_variograms,
    settings,
    simulated,
    statistics,
    view_controls,
):
    _name = view_controls.value["parameter"]
    _log = saved_variograms[_name]["transform"] == "log10"
    _cpt = samples.filter(pl.col("bro_id") == check_cpt.value)
    _x, _y = _cpt["x"][0], _cpt["y"][0]
    # The column of cells the CPT lies in
    _column = cells.filter(
        ((pl.col("x") - _x).abs() <= settings["horizontal"] / 2) & ((pl.col("y") - _y).abs() <= settings["horizontal"] / 2)
    ).sort("z")
    _index = _column["cell"].to_numpy()
    _realisations = pl.DataFrame(
        {
            "z": np.tile(_column["z"].to_numpy(), settings["realisations"]),
            "realisation": np.repeat(np.arange(settings["realisations"]) + 1, len(_index)),
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
        alt.Chart(_realisations)
        .mark_line(strokeWidth=0.6, opacity=0.5, color="#4c78a8")
        .encode(x=alt.X("value:Q", title=_title, scale=_x_scale), y=alt.Y("z:Q", title="z (m NAP)"), detail="realisation:N", order="z:Q")
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
            mo.md(f"{check_cpt.value} at x = {_x:.0f}, y = {_y:.0f}, in the column of cells of {settings['horizontal']:g} × {settings['horizontal']:g} m around it."),
            (_area + _lines + _median + _points).properties(width=420, height=440),
        ]
    )
    return


@app.cell(hide_code=True)
def runs_intro(mo):
    mo.md(r"""
    ## 4 · The saved runs

    Each run of a parameter is saved in `data/simulations/` as soon as it is simulated, as NetCDF: the
    realisations on the regular grid (realisation × z × y × x, in RD New and m NAP, NaN outside the
    simulation domains), each cell's domain, and the run's definition. Its name ends in a hash of that
    definition (the parameter's variograms, the simulation domains, the resolution, the number of
    realisations and the seed), so Simulate reads a run with the same definition instead of simulating it
    again. The runs shown above are marked.
    """)
    return


@app.cell(hide_code=True)
def saved_runs(
    SAVE_DATES,
    SIMULATIONS_DIR,
    domain_definition,
    json,
    mo,
    pl,
    saved_variograms,
    simulation_files,
    xr,
):
    # The runs saved in SIMULATIONS_DIR, from their definitions
    _rows = []
    for _path in sorted(SIMULATIONS_DIR.glob("*.nc")):
        with xr.open_dataset(_path, engine="h5netcdf") as _dataset:
            _definition = json.loads(_dataset.attrs["definition"])
            _rows.append(
                {
                    "shown": _path in simulation_files.values(),
                    "parameter": _definition["parameter"],
                    "horizontal (m)": _definition["resolution"]["horizontal"],
                    "vertical (m)": _definition["resolution"]["vertical"],
                    "realisations": _definition["realisations"],
                    "seed": _definition["seed"],
                    # Whether the run is of the variograms and simulation domains saved now
                    "current inputs": _definition["variograms"]
                    == {_k: _v for _k, _v in saved_variograms.get(_definition["parameter"], {}).items() if _k not in SAVE_DATES}
                    and _definition["simulation_domains"] == {_k: _v for _k, _v in domain_definition.items() if _k != "saved"},
                    "created": _dataset.attrs["created"],
                    "minutes": round(_dataset.attrs["seconds"] / 60, 1),
                    "MB": round(_path.stat().st_size / 1e6, 1),
                    "file": _path.name,
                }
            )
    mo.ui.table(pl.DataFrame(_rows), selection=None) if _rows else mo.md("No runs are saved yet.")
    return


if __name__ == "__main__":
    app.run()
