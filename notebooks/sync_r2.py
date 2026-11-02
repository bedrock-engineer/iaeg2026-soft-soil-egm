# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "h5netcdf==1.8.2",
#     "h5py==3.16.0",
#     "marimo>=0.25.2",
#     "marimo-lens==0.2.4",
#     "numpy",
#     "obstore>=0.11.1",
#     "polars==2.1.0",
#     "pyarrow",
#     "wigglystuff==0.5.36",
#     "xarray==2026.9.0",
#     "zarr>=3",
# ]
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def imports():
    import json
    import os
    from pathlib import Path
    from urllib.parse import urlsplit

    import marimo as mo
    import numpy as np
    import obstore
    import polars as pl
    import xarray as xr
    from marimo_lens import Lens
    from obstore.store import S3Store
    from wigglystuff import EnvConfig

    return (
        EnvConfig,
        Lens,
        Path,
        S3Store,
        json,
        mo,
        np,
        obstore,
        os,
        pl,
        urlsplit,
        xr,
    )


@app.cell(hide_code=True)
def lens_widget(Lens):
    # marimo-lens: select a region of any output and add a note for the notebook agent
    lens = Lens()
    lens
    return


@app.cell(hide_code=True)
def intro(mo):
    mo.md(r"""
    # Sync R2

    Puts the results of one run on Cloudflare R2, for the GitHub Page, under names that do not change with the run:

    - `soil_model.zarr/<height>cm/`: on the run's grid, the P10, P50 and P90 of qc, fs and Ic, the most likely soil
      behavior type (SBTn) and the probability of each, the simulation domain, GeoTOP's stratigraphic unit and
      lithology class. Without the realizations, which stay in `data/simulations/`. Zarr, so that the page only
      fetches the chunks that a view needs; a group per height, so that other heights can be added later.
    - `soil_model_<height>cm.json`: the decisions behind it: the selection of `01`, and the simulation domains,
      variograms, resolution, realizations and seed of the run, and the settings of its classification.
    - `cpts.parquet`: the CPT readings as `01` read them from the BRO.
    - `cpts_interpreted_<height>cm.parquet`, `sbtn_volumes_<height>cm.parquet` and
      `rvt_advanced_sample_combined_arch_str.parquet`: the GeoParquet BimDataFrames of `06_bimdataframes.py`: the CPTs'
      layers as cylinders, the SBTn volumes of the run and Revit's advanced sample project, all in the site's CRS.

    The 10 m / 25 cm run is selected to start with: section 4 of `05_cpt_classification.py` shows that 10 cm adds no
    support away from the CPTs.
    """)
    return


@app.cell
def inputs(Path, mo):
    DATA_DIR = Path(mo.notebook_dir()).parent / "data"
    NOTEBOOKS_DIR = Path(mo.notebook_dir())
    # m, the height of GeoTOP's voxels and the width of its columns
    VOXEL = 0.5
    COLUMN = 100.0
    # Where the Zarr store and .json are written before they go to R2
    SYNC_DIR = DATA_DIR / "r2"
    # The run that goes to R2, unless another is selected
    SYNCED_RUN = "qc-fs_9c84e017d7ae.nc"
    # Cells per chunk. About as many along each axis, so that a plan and both sections each touch a few chunks.
    CHUNKS = {"z": 50, "y": 25, "x": 30}
    return CHUNKS, COLUMN, DATA_DIR, NOTEBOOKS_DIR, SYNCED_RUN, SYNC_DIR, VOXEL


@app.cell(hide_code=True)
def saved_runs(DATA_DIR, NOTEBOOKS_DIR, SYNCED_RUN, json, mo, pl, xr):
    # The classified runs. A run has current inputs when its variograms and simulation domains are the ones
    # saved now.
    _domains_now = {
        _k: _v for _k, _v in json.loads((NOTEBOOKS_DIR / "simulation_domains.json").read_text(encoding="utf-8")).items() if _k != "saved"
    }
    _variograms_now = json.loads((NOTEBOOKS_DIR / "variograms.json").read_text(encoding="utf-8"))


    def _current(definition):
        _at_height = _variograms_now.get(f"{definition['resolution']['vertical']:g}", {})
        return definition["simulation_domains"] == _domains_now and all(
            _variograms == {_k: _v for _k, _v in _at_height.get(_name, {}).items() if _k not in ("saved", "simulation_domains_saved")}
            for _name, _variograms in definition["variograms"].items()
        )


    _rows = []
    for _path in (DATA_DIR / "cpt_classification").glob("*.nc"):
        _run_path = DATA_DIR / "simulations" / f"{_path.stem.rsplit('_', 1)[0]}.nc"
        if not _run_path.exists():
            continue
        with xr.open_dataset(_run_path, engine="h5netcdf") as _run:
            _definition = json.loads(_run.attrs["definition"])
            _rows.append(
                {
                    "horizontal (m)": _definition["resolution"]["horizontal"],
                    "vertical (m)": _definition["resolution"]["vertical"],
                    "realizations": _definition["realizations"],
                    "seed": _definition["seed"],
                    "current inputs": _current(_definition),
                    "created": _run.attrs["created"],
                    "run": _run_path.name,
                    "classification": _path.name,
                }
            )
    mo.stop(not _rows, mo.md("Classify a run in `05_cpt_classification.py` first."))
    _runs = pl.DataFrame(_rows).sort("created", descending=True)
    saved_runs = mo.ui.table(
        _runs,
        selection="single",
        initial_selection=[_runs["run"].to_list().index(SYNCED_RUN) if SYNCED_RUN in _runs["run"] else 0],
        label="Classified runs",
    )
    saved_runs
    return (saved_runs,)


@app.cell(hide_code=True)
def soil_model(
    CHUNKS,
    COLUMN,
    DATA_DIR,
    SYNC_DIR,
    VOXEL,
    json,
    mo,
    np,
    pl,
    saved_runs,
    xr,
):
    mo.stop(saved_runs.value.is_empty(), mo.md("Select a run in the table above."))
    _run_name, _classification_name = saved_runs.value["run"][0], saved_runs.value["classification"][0]


    def _categories(values, names, description):
        """Codes on the grid, as CF flags: names may not hold spaces there"""
        return (
            ("z", "y", "x"),
            values,
            {
                "description": description,
                "flag_values": list(range(len(names))),
                "flag_meanings": " ".join(_name.replace(" ", "_") for _name in names),
                "missing_value": -1,
            },
        )


    _percentiles = [f"{_name}_p{_p}" for _name in ("qc", "fs") for _p in (10, 50, 90)]
    with (
        xr.open_dataset(DATA_DIR / "simulations" / _run_name, engine="h5netcdf") as _run,
        xr.open_dataset(DATA_DIR / "cpt_classification" / _classification_name, engine="h5netcdf") as _classification,
    ):
        _x, _y, _z = (_run[_axis].values for _axis in ("x", "y", "z"))
        # GeoTOP's voxels on the run's grid: a voxel's x and y are its south-west corner, its z its center, and
        # the grid's coordinates are the centers of the cells
        _voxels = pl.read_parquet(DATA_DIR / "voxel_domains.parquet")
        _voxel_x, _voxel_y, _voxel_z = (np.sort(_voxels[_axis].unique().to_numpy()) for _axis in ("x", "y", "z"))
        _cell = np.ix_(
            np.searchsorted(_voxel_z, np.round(_z / VOXEL) * VOXEL),
            np.searchsorted(_voxel_y, _y // COLUMN * COLUMN),
            np.searchsorted(_voxel_x, _x // COLUMN * COLUMN),
        )


        def _on_grid(column):
            _names = _voxels[column].unique().sort().to_list()
            _codes = _voxels[column].replace_strict({_name: _i for _i, _name in enumerate(_names)}, return_dtype=pl.Int8).to_numpy()
            _grid = np.full((len(_voxel_z), len(_voxel_y), len(_voxel_x)), -1, dtype=np.int8)
            _grid[
                np.searchsorted(_voxel_z, _voxels["z"].to_numpy()),
                np.searchsorted(_voxel_y, _voxels["y"].to_numpy()),
                np.searchsorted(_voxel_x, _voxels["x"].to_numpy()),
            ] = _codes
            return _grid[_cell], _names


        _soil_behavior_types = json.loads(_classification.attrs["soil_behavior_types"])
        _zones = [int(_zone) for _zone in _classification["zone"].values]
        _domains = _classification["domain"].fillna(-1).values.astype(np.int8)
        _units, _unit_names = _on_grid("stratigraphic_unit")
        _classes, _class_names = _on_grid("grondsoort")
        soil_model = xr.Dataset(
            {
                **{_name: _run[_name].load() for _name in _percentiles},
                **{_name: _classification[_name].load() for _name in ("ic_p10", "ic_p50", "ic_p90")},
                "sbtn_most_likely": _classification["most_likely_zone"].load().assign_attrs(
                    description="The most likely SBTn zone, 0 outside the simulation domains"
                ),
                "sbtn_probability": _classification["zone_probability"].load().rename(zone="sbtn_zone").assign_attrs(
                    description="Share of the realizations in each SBTn zone"
                ),
                "domain": _categories(_domains, _classification["domain"].attrs["flag_meanings"].split(), "Simulation domain"),
                "stratigraphic_unit": _categories(_units, _unit_names, "GeoTOP's stratigraphic unit of the voxel the cell lies in"),
                "geotop_lithology_class": _categories(_classes, _class_names, "GeoTOP's lithology class of the voxel the cell lies in"),
            },
            coords={"sbtn_zone": _zones, "z": _z, "y": _y, "x": _x},
            attrs={
                "crs": _run.attrs["crs"],
                "coordinates": "x, y and z are the centers of the cells",
                "soil_behavior_types": json.dumps(_soil_behavior_types, ensure_ascii=False),
                "run": _run_name,
                "classification": _classification_name,
            },
        )
        # The decisions behind it: of 01, and of 02, 03 and 04 as the run saved them, and of 05
        decisions = {
            "selection": json.loads((DATA_DIR / "selection.json").read_text(encoding="utf-8")),
            "simulation": json.loads(_run.attrs["definition"]),
            "classification": {**json.loads(_classification.attrs["definition"]), "soil_behavior_types": _soil_behavior_types},
        }

    SYNC_DIR.mkdir(exist_ok=True)
    SYNC_HEIGHT = f"{saved_runs.value['vertical (m)'][0] * 100:g}cm"
    soil_model_store = SYNC_DIR / "soil_model.zarr"
    decisions_path = SYNC_DIR / f"soil_model_{SYNC_HEIGHT}.json"
    # A zone's probability is one array of chunks per zone, since a view shows one zone at a time
    soil_model.to_zarr(
        soil_model_store,
        group=SYNC_HEIGHT,
        mode="w",
        zarr_format=3,
        consolidated=False,
        encoding={
            _name: {"chunks": tuple(1 if _dim == "sbtn_zone" else CHUNKS[_dim] for _dim in soil_model[_name].dims)}
            for _name in soil_model.data_vars
        },
    )
    decisions_path.write_text(json.dumps(decisions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    soil_model
    return SYNC_HEIGHT, decisions_path, soil_model_store


@app.cell(hide_code=True)
def r2_settings(EnvConfig, mo, os):
    # The S3 API URL is not secret, so it is a plain text field; the keys stay hidden
    r2_s3_api = mo.ui.text(
        value=os.environ.get("R2_S3_API", ""),
        placeholder="https://<account id>.eu.r2.cloudflarestorage.com/<bucket>",
        label="R2_S3_API",
        full_width=True,
    )
    r2_config = mo.ui.anywidget(EnvConfig(["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"]))
    r2_prefix = mo.ui.text(
        value="nl-amsterdam-noord",
        label="Prefix",
        full_width=True,
    )
    mo.vstack(
        [
            mo.md(r"""
    ## Pushing to Cloudflare R2

    The R2 credentials come from the environment or the widget below, and are never written to disk.
    `R2_S3_API` is the bucket's S3 API URL as the Cloudflare dashboard shows it under R2, the bucket, Settings:
    `https://<account id>.eu.r2.cloudflarestorage.com/<bucket>`.
    """),
            r2_s3_api,
            r2_config,
            r2_prefix,
        ]
    )
    return r2_config, r2_prefix, r2_s3_api


@app.cell(hide_code=True)
def r2_files(
    DATA_DIR,
    SYNC_HEIGHT,
    decisions_path,
    mo,
    pl,
    r2_prefix,
    saved_runs,
    soil_model_store,
):
    # What goes to R2: every file of the height's Zarr group and the store's own metadata, and the other files under
    # names without the run
    _prefix = r2_prefix.value.strip("/")
    _interpreted = DATA_DIR / "bimdataframes" / f"cpts_interpreted_{SYNC_HEIGHT}.parquet"
    _volumes = DATA_DIR / "bimdataframes" / f"sbtn_volumes_{saved_runs.value['run'][0].removesuffix('.nc')}.parquet"
    _revit = DATA_DIR / "bimdataframes" / "rvt_advanced_sample_combined_arch_str.parquet"
    mo.stop(
        not (_interpreted.exists() and _volumes.exists() and _revit.exists()),
        mo.md(f"Select this run in `06_bimdataframes.py` first, which writes `{_interpreted.name}`, `{_volumes.name}` and `{_revit.name}`."),
    )
    _zarr = {
        f"{_prefix}/{soil_model_store.name}/{_path.relative_to(soil_model_store).as_posix()}": _path
        for _path in [soil_model_store / "zarr.json", *(soil_model_store / SYNC_HEIGHT).rglob("*")]
        if _path.is_file()
    }
    _files = {
        f"{_prefix}/{decisions_path.name}": decisions_path,
        f"{_prefix}/cpts.parquet": DATA_DIR / "cpts.parquet",
        f"{_prefix}/{_interpreted.name}": _interpreted,
        f"{_prefix}/sbtn_volumes_{SYNC_HEIGHT}.parquet": _volumes,
        f"{_prefix}/{_revit.name}": _revit,
    }
    r2_uploads = _zarr | _files
    push_button = mo.ui.run_button(label=f"Push {len(r2_uploads)} files to R2")
    mo.vstack(
        [
            pl.DataFrame(
                [
                    {
                        "url_path": f"{_prefix}/{soil_model_store.name}/{SYNC_HEIGHT}/",
                        "files": len(_zarr),
                        "mb": round(sum(_path.stat().st_size for _path in _zarr.values()) / 1e6, 1),
                    },
                    *({"url_path": _key, "files": 1, "mb": round(_path.stat().st_size / 1e6, 1)} for _key, _path in _files.items()),
                ]
            ),
            push_button,
        ]
    )
    return push_button, r2_uploads


@app.cell(hide_code=True)
def r2_store(S3Store, mo, r2_config, r2_s3_api, urlsplit):
    # The S3 API URL is the account's endpoint followed by the bucket
    _url = urlsplit(r2_s3_api.value.strip())
    _bucket = _url.path.strip("/")
    mo.stop(
        not (_url.scheme and _url.netloc and _bucket and r2_config.all_valid),
        mo.md("Set the R2 fields above."),
    )
    r2_store = S3Store(
        _bucket,
        endpoint=f"{_url.scheme}://{_url.netloc}",
        access_key_id=r2_config["R2_ACCESS_KEY_ID"],
        secret_access_key=r2_config["R2_SECRET_ACCESS_KEY"],
        region="auto",
    )
    return (r2_store,)


@app.cell(hide_code=True)
def push(mo, obstore, push_button, r2_store, r2_uploads):
    mo.stop(not push_button.value, mo.md("Press **Push** to upload. Existing keys are overwritten."))
    for _key, _path in mo.status.progress_bar(list(r2_uploads.items()), title="Pushing"):
        obstore.put(r2_store, _key, _path.read_bytes())
    pushed = list(r2_uploads)
    return (pushed,)


@app.cell(hide_code=True)
def r2_listing(obstore, pl, pushed, r2_prefix, r2_store):
    # What lies under the prefix, read back from R2 after a push
    pushed
    pl.DataFrame(
        [
            {"key": _meta["path"], "mb": _meta["size"] / 1e6, "last_modified": _meta["last_modified"]}
            for _batch in obstore.list(r2_store, prefix=r2_prefix.value.strip("/"))
            for _meta in _batch
        ]
    )
    return


if __name__ == "__main__":
    app.run()
