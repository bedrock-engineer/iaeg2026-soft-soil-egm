# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "bimpolars[speckle]",
#     "h5netcdf==1.8.2",
#     "h5py==3.16.0",
#     "marimo>=0.25.2",
#     "marimo-lens==0.2.4",
#     "numpy",
#     "polars==2.1.0",
#     "pyarrow",
#     "pyproj==3.8.0",
#     "pyvista",
#     "specklewidgets",
#     "wigglystuff==0.5.36",
#     "xarray==2026.9.0",
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
    # BimDataFrames

    A classified run from `05_cpt_classification.py` as two bimpolars BimDataFrames, in the same site CRS as the
    GeoTOP voxels of `01_get_data.py`, written as GeoParquet to `data/bimdataframes/` for `sync_r2.py`:

    - **The interpreted CPTs:** each CPT's samples of the run's height, classified with `robertson` as in `05`.
      Consecutive samples of the same soil behavior type (SBTn) merge into one cylinder per layer, wider than
      the cone so that it remains visible.
    - **The SBTn volumes:** all cells with the same most likely SBTn merge into one volume, the outer surface of
      those cells. A volume can consist of several separate parts. The volumes leave out a pit, where the CPTs and part of the foundations stand free.

    Each row carries the summary statistics of what it merges, in the property set `CPT` or `SBTn volume`.
    """)
    return


@app.cell
def _():
    import json
    from pathlib import Path

    import bimpolars as bpl
    import marimo as mo
    import numpy as np
    import polars as pl
    import pyproj
    import pyvista as pv
    import xarray as xr
    from marimo_lens import Lens
    from specklewidgets import GeoSpeckleViewer, models_gz
    from specklewidgets.bim import bim_objects
    from specklewidgets.geo import pdok_3d_buildings
    from specklewidgets.server import DEFAULT_SERVER, local_client, send, token_client
    from wigglystuff import EnvConfig

    from cpt_robertson_classification import SOIL_BEHAVIOR_COLORS, SOIL_BEHAVIOR_TYPES, robertson

    # RD New + NAP to WGS 84 follows RDNAPTRANS2018 only with the NSGI grids, which PROJ fetches
    pyproj.network.set_network_enabled(True)
    return (
        DEFAULT_SERVER,
        EnvConfig,
        GeoSpeckleViewer,
        Lens,
        Path,
        SOIL_BEHAVIOR_COLORS,
        SOIL_BEHAVIOR_TYPES,
        bim_objects,
        bpl,
        json,
        local_client,
        mo,
        models_gz,
        np,
        pdok_3d_buildings,
        pl,
        pv,
        robertson,
        send,
        token_client,
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
    BIMDATAFRAMES_DIR = DATA_DIR / "bimdataframes"
    # m, GeoTOP's columns, the height of its voxels and the radius of a CPT's cylinders; the sides of a cylinder
    COLUMN = 100.0
    VOXEL = 0.5
    # A pit to see the CPTs and part of the foundations in, in RD New meters: the SBTn volumes leave it out
    PIT = {"x": (121800, 122080), "y": (488650, 488770)}
    CPT_RADIUS = 1.0
    CPT_SIDES = 16
    return (
        BIMDATAFRAMES_DIR,
        COLUMN,
        CPT_RADIUS,
        CPT_SIDES,
        DATA_DIR,
        PIT,
        VOXEL,
    )


@app.cell(hide_code=True)
def read_inputs(DATA_DIR, SOIL_BEHAVIOR_TYPES, VOXEL, bpl, mo, pl):
    _voxels_path, _geotop_path = DATA_DIR / "voxel_domains.parquet", DATA_DIR / "geotop_bimdf.parquet"
    mo.stop(
        not (_voxels_path.exists() and _geotop_path.exists()),
        mo.md("Run `01_get_data.py` and save the simulation domains in `02_simulation_domains.py` first."),
    )
    voxels = pl.read_parquet(_voxels_path)
    # The ground per GeoTOP column: the top of its highest voxel
    ground_levels = voxels.group_by("x", "y").agg((pl.col("z").max() + VOXEL / 2).alias("ground_level"))
    # The CRS the GeoTOP voxels lie in, so that the CPTs and volumes line up with them
    site_crs = bpl.read_parquet(_geotop_path).crs
    SBTN_LABELS = {_zone: f"{_zone} {_name}" for _zone, _name in SOIL_BEHAVIOR_TYPES.items()}
    return SBTN_LABELS, ground_levels, site_crs, voxels


@app.cell(hide_code=True)
def saved_runs(DATA_DIR, json, mo, pl, xr):
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
                    "created": _run.attrs["created"],
                    "run": _run_path.name,
                    "classification": _path.name,
                }
            )
    mo.stop(not _rows, mo.md("Classify a run in `05_cpt_classification.py` first."))
    saved_runs = mo.ui.table(
        pl.DataFrame(_rows).sort("created", descending=True),
        selection="single",
        initial_selection=[1],
        label="Classified runs",
    )
    saved_runs
    return (saved_runs,)


@app.cell(hide_code=True)
def merge_statistics(pl):
    def statistics(columns):
        """The median, minimum and maximum of columns that merge"""
        return [
            _stat
            for _name in columns
            for _stat in (
                pl.col(_name).median().alias(f"{_name}_median"),
                pl.col(_name).min().alias(f"{_name}_min"),
                pl.col(_name).max().alias(f"{_name}_max"),
            )
        ]


    def dominant(columns):
        """The most common value of categories that merge, the first by name when tied, and its share"""
        return [
            _stat
            for _name in columns
            for _stat in (
                pl.col(_name).drop_nulls().mode().sort().first().alias(f"{_name}_dominant"),
                (pl.col(_name) == pl.col(_name).drop_nulls().mode().sort().first()).mean().alias(f"{_name}_dominant_share"),
            )
        ]

    return dominant, statistics


@app.cell(hide_code=True)
def bim_elements(SOIL_BEHAVIOR_COLORS, bpl, np, pl, site_crs):
    def elements(frame, vertices, faces, property_set):
        """A BimDataFrame in the site CRS, one row per row of frame, which holds its id, name, sbtn and
        sbtn_zone. Each has vertices (n × 3) in RD New + NAP and triangles (m × 3), in its SBTn's color; frame
        without id and name becomes its property set."""
        _bounds = np.array([[*_v.min(axis=0), *_v.max(axis=0)] for _v in vertices])
        _hex = pl.col("sbtn_zone").replace_strict(SOIL_BEHAVIOR_COLORS, return_dtype=pl.String)
        _rgb = [_hex.str.slice(_i, 2).str.to_integer(base=16) / 255 for _i in (1, 3, 5)]
        _rd = bpl.BimDataFrame(
            frame.select(
                "id",
                "name",
                **{"class": pl.col("sbtn").cast(pl.Categorical)},
                properties=pl.struct(pl.struct(pl.all().exclude("id", "name")).alias(property_set)),
                mesh=pl.struct(
                    vertices=pl.Series([_v.ravel().tolist() for _v in vertices], dtype=pl.List(pl.Float64)),
                    faces=pl.Series([_f.ravel().tolist() for _f in faces], dtype=pl.List(pl.UInt32)),
                    styles=pl.concat_list(
                        pl.struct(
                            name=pl.col("sbtn"),
                            rgba=pl.concat_list(*_rgb, pl.lit(1.0)).list.to_array(4),
                            face_count=pl.Series([len(_f) for _f in faces], dtype=pl.UInt32),
                        )
                    ),
                ).cast(bpl.MESH_DTYPE),
                bbox=pl.struct(
                    **{_name: pl.Series(_bounds[:, _i]) for _i, _name in enumerate(("xmin", "ymin", "zmin", "xmax", "ymax", "zmax"))}
                ),
                # A footprint lies at the level of a row's container, or else of the row itself
                container=pl.lit(None, dtype=pl.String),
                elevation=pl.lit(None, dtype=pl.Float64),
            ),
            crs="EPSG:7415",
        )
        # The footprints and their place in longitude and latitude make it a GeoParquet
        return bpl.with_geog(bpl.to_crs(bpl.simple_features(_rd), site_crs))

    return (elements,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1 · The interpreted CPTs
    """)
    return


@app.cell(hide_code=True)
def classified(
    DATA_DIR,
    SBTN_LABELS,
    VOXEL,
    ground_levels,
    json,
    mo,
    np,
    pl,
    robertson,
    saved_runs,
    voxels,
    xr,
):
    mo.stop(saved_runs.value.is_empty(), mo.md("Select a run in the table above."))
    SAMPLE_HEIGHT = saved_runs.value["vertical (m)"][0]
    _samples_path = DATA_DIR / f"simulation_samples_{SAMPLE_HEIGHT * 100:g}cm.parquet"
    mo.stop(not _samples_path.exists(), mo.md("Save the variograms of this run's vertical resolution in `03_variograms.py` first."))
    with xr.open_dataset(DATA_DIR / "cpt_classification" / saved_runs.value["classification"][0], engine="h5netcdf") as _classification:
        _gamma_missing = json.loads(_classification.attrs["definition"])["gamma_missing"]
    # The CPT samples with a qc and fs, classified as in 05: on all levels of their height in GeoTOP's voxels, so
    # that what lies above them weighs as above the cells
    _usable = (
        pl.read_parquet(_samples_path)
        .filter((pl.col("qc") > 0) & (pl.col("fs") > 0))
        .join(ground_levels, left_on=["column_x", "column_y"], right_on=["x", "y"])
    )
    _ids = _usable["bro_id"].unique().sort().to_list()
    _offsets = -VOXEL / 2 + (np.arange(round(VOXEL / SAMPLE_HEIGHT)) + 0.5) * SAMPLE_HEIGHT
    _levels = np.unique(np.round(voxels["z"].unique().to_numpy()[:, None] + _offsets, 3))[::-1]
    _rows = _usable["bro_id"].replace_strict({_b: _i for _i, _b in enumerate(_ids)}, return_dtype=pl.Int64).to_numpy()
    _depths = np.searchsorted(-_levels, -_usable["z"].to_numpy())
    _qc, _fs = np.full((2, len(_ids), len(_levels)), np.nan)
    _qc[_rows, _depths] = _usable["qc"].to_numpy()
    _fs[_rows, _depths] = _usable["fs"].to_numpy()
    _ground = _usable.group_by("bro_id").agg(pl.first("ground_level")).sort("bro_id")["ground_level"].to_numpy()
    _result = robertson(_qc, _fs, _levels, _ground, gamma_missing=_gamma_missing)
    classified_cpts = _usable.with_columns(
        *(pl.Series(_name, _result[_name][_rows, _depths]) for _name in ("ic", "qtn", "fr")),
        pl.Series("sbtn_zone", _result["zone"][_rows, _depths], dtype=pl.Int64),
    ).with_columns(sbtn=pl.col("sbtn_zone").replace_strict(SBTN_LABELS, return_dtype=pl.String))
    return SAMPLE_HEIGHT, classified_cpts


@app.cell(hide_code=True)
def cpt_layers(SAMPLE_HEIGHT, classified_cpts, dominant, pl, statistics):
    # Consecutive samples of a CPT of the same SBTn, from the top down, with the statistics of what they merge. A
    # level without a sample also ends a layer.
    cpt_layers = (
        classified_cpts.sort(["bro_id", "z"], descending=[False, True])
        .with_columns(
            layer=(
                (pl.col("sbtn_zone") != pl.col("sbtn_zone").shift(1))
                | ((pl.col("z").shift(1) - pl.col("z")).round(3) > SAMPLE_HEIGHT)
            )
            .fill_null(True)
            .cum_sum()
            .over("bro_id")
        )
        .group_by("bro_id", "x", "y", "layer", "sbtn_zone", "sbtn", maintain_order=True)
        .agg(
            top_z=pl.col("z").max() + SAMPLE_HEIGHT / 2,
            bottom_z=pl.col("z").min() - SAMPLE_HEIGHT / 2,
            samples=pl.len(),
            readings=pl.col("readings").sum(),
            *statistics(["qc", "fs", "rf", "ic", "qtn", "fr"]),
            *dominant(["domain", "stratigraphic_unit", "grondsoort"]),
        )
        .with_columns(
            thickness=pl.col("top_z") - pl.col("bottom_z"),
            id=pl.format("cpt {} layer {}", "bro_id", "layer"),
            name=pl.format("{}, {}", "bro_id", "sbtn"),
        )
    )
    cpt_layers
    return (cpt_layers,)


@app.cell(hide_code=True)
def cpt_cylinders(
    BIMDATAFRAMES_DIR,
    CPT_RADIUS,
    CPT_SIDES,
    SAMPLE_HEIGHT,
    cpt_layers,
    elements,
    np,
    pv,
):
    # One cylinder of height 1 at the origin, stretched and moved to each layer. PyVista's points are single
    # precision, which RD New's coordinates need more than.
    _cylinder = pv.Cylinder(center=(0, 0, 0), direction=(0, 0, 1), radius=CPT_RADIUS, height=1.0, resolution=CPT_SIDES, capping=True).triangulate()
    _points = np.asarray(_cylinder.points, dtype=np.float64)
    _faces = np.asarray(_cylinder.regular_faces)
    _vertices = [
        _points * [1.0, 1.0, _top - _bottom] + [_x, _y, (_top + _bottom) / 2]
        for _x, _y, _top, _bottom in cpt_layers.select("x", "y", "top_z", "bottom_z").iter_rows()
    ]
    cpts_bimdf = elements(cpt_layers, _vertices, [_faces] * len(_vertices), "CPT")
    BIMDATAFRAMES_DIR.mkdir(exist_ok=True)
    cpts_bimdf.write_parquet(BIMDATAFRAMES_DIR / f"cpts_interpreted_{SAMPLE_HEIGHT * 100:g}cm.parquet")
    cpts_bimdf
    return (cpts_bimdf,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2 · The SBTn volumes
    """)
    return


@app.cell(hide_code=True)
def run_cells(
    COLUMN,
    DATA_DIR,
    PIT,
    SBTN_LABELS,
    VOXEL,
    np,
    pl,
    saved_runs,
    voxels,
    xr,
):
    # The cells in a simulation domain and outside the pit with their values, and the stratigraphic unit and lithology class of the
    # GeoTOP voxel they lie in. "cell" is the cell's place in the grid, x going fastest, then y, then z.
    with (
        xr.open_dataset(DATA_DIR / "simulations" / saved_runs.value["run"][0], engine="h5netcdf") as _run,
        xr.open_dataset(DATA_DIR / "cpt_classification" / saved_runs.value["classification"][0], engine="h5netcdf") as _classification,
    ):
        most_likely_grid = _classification["most_likely_zone"].values.astype(np.int8)
        grid_axes = {_axis: _run[_axis].values for _axis in ("x", "y", "z")}
        _in_pit = [(grid_axes[_axis] > PIT[_axis][0]) & (grid_axes[_axis] < PIT[_axis][1]) for _axis in ("y", "x")]
        most_likely_grid[:, np.outer(*_in_pit)] = 0
        _iz, _iy, _ix = np.nonzero(most_likely_grid > 0)
        _most_likely = most_likely_grid[_iz, _iy, _ix]
        _names = np.array(_classification["domain"].attrs["flag_meanings"].split())
        run_cells = pl.DataFrame(
            {
                "cell": np.ravel_multi_index((_iz, _iy, _ix), most_likely_grid.shape),
                "x": grid_axes["x"][_ix],
                "y": grid_axes["y"][_iy],
                "z": grid_axes["z"][_iz],
                "sbtn_zone": _most_likely.astype(np.int64),
                "domain": _names[_classification["domain"].values[_iz, _iy, _ix].astype(int)],
                "sbtn_probability": _classification["zone_probability"].values[_most_likely - 1, _iz, _iy, _ix],
                **{_name: _run[f"{_name}_p50"].values[_iz, _iy, _ix] for _name in ("qc", "fs")},
                "ic": _classification["ic_p50"].values[_iz, _iy, _ix],
                "ic_spread": (_classification["ic_p90"] - _classification["ic_p10"]).values[_iz, _iy, _ix],
            }
        )
    run_cells = (
        run_cells.with_columns(
            voxel_x=(pl.col("x") // COLUMN) * COLUMN, voxel_y=(pl.col("y") // COLUMN) * COLUMN, voxel_z=(pl.col("z") / VOXEL).round() * VOXEL
        )
        .join(
            voxels.select(voxel_x="x", voxel_y="y", voxel_z="z", stratigraphic_unit="stratigraphic_unit", grondsoort="grondsoort"),
            on=["voxel_x", "voxel_y", "voxel_z"],
            how="left",
            maintain_order="left",
        )
        .with_columns(sbtn=pl.col("sbtn_zone").replace_strict(SBTN_LABELS, return_dtype=pl.String))
    )
    return grid_axes, most_likely_grid, run_cells


@app.cell(hide_code=True)
def sbtn_volumes(
    BIMDATAFRAMES_DIR,
    SBTN_LABELS,
    dominant,
    elements,
    grid_axes,
    most_likely_grid,
    np,
    pl,
    pv,
    run_cells,
    saved_runs,
    statistics,
):
    # The grid as PyVista cells, around its first cell: PyVista's points are single precision, which RD New's
    # coordinates need more than
    _origin = np.array([grid_axes[_axis][0] for _axis in ("x", "y", "z")])
    _size = [float(saved_runs.value["horizontal (m)"][0])] * 2 + [float(saved_runs.value["vertical (m)"][0])]


    def _edges(centers, size):
        return np.append(centers, centers[-1] + size) - size / 2


    _grid = pv.RectilinearGrid(*(_edges(grid_axes[_axis] - _o, _s) for _axis, _o, _s in zip(("x", "y", "z"), _origin, _size)))
    _grid.cell_data["sbtn_zone"] = most_likely_grid.ravel()

    # One surface per SBTn, as far as it is most likely somewhere
    _vertices, _faces, _parts = [], [], []
    _zones = [int(_zone) for _zone in np.unique(most_likely_grid) if _zone > 0]
    for _zone in _zones:
        _cells = _grid.threshold([_zone - 0.5, _zone + 0.5], scalars="sbtn_zone", preference="cell")
        _surface = _cells.extract_surface(algorithm="dataset_surface").triangulate().clean()
        _vertices.append(np.asarray(_surface.points, dtype=np.float64) + _origin)
        _faces.append(np.asarray(_surface.regular_faces))
        _parts.append(int(_cells.connectivity(extraction_mode="all").cell_data["RegionId"].max()) + 1)

    _cell_volume = float(np.prod(_size))
    # The statistics of what each volume merges, in the order of the surfaces
    volume_statistics = (
        run_cells.group_by("sbtn_zone", "sbtn")
        .agg(
            cells=pl.len(),
            volume_m3=pl.len() * _cell_volume,
            top_z=pl.col("z").max() + _size[2] / 2,
            bottom_z=pl.col("z").min() - _size[2] / 2,
            *statistics(["qc", "fs", "ic", "ic_spread", "sbtn_probability"]),
            *dominant(["domain", "stratigraphic_unit", "grondsoort"]),
        )
        .sort("sbtn_zone")
        .with_columns(
            pl.Series("parts", _parts),
            model_share=pl.col("volume_m3") / pl.col("volume_m3").sum(),
            id=pl.format("sbtn volume {}", "sbtn_zone"),
            name=pl.col("sbtn"),
        )
    )
    assert volume_statistics["sbtn_zone"].to_list() == _zones and set(_zones) <= set(SBTN_LABELS)
    volumes_bimdf = elements(volume_statistics, _vertices, _faces, "SBTn volume")
    BIMDATAFRAMES_DIR.mkdir(exist_ok=True)
    volumes_bimdf.write_parquet(BIMDATAFRAMES_DIR / f"sbtn_volumes_{saved_runs.value['run'][0].removesuffix('.nc')}.parquet")
    volume_statistics
    return (volumes_bimdf,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3 · In the GeoSpeckleViewer

    Among the buildings of PDOK's 3D BAG. Check what to show on the right, and uncheck an SBTn to see into the volumes:
    the view then goes back to the whole model. Click an element to see its row below.
    """)
    return


@app.cell(hide_code=True)
def revit_foundations(bpl, pl, site_crs):
    # The piles and pile caps of Revit's advanced sample project, placed in Amsterdam Noord, in the site's CRS
    foundations_bimdf = bpl.to_crs(
        bpl.read_parquet(
            "https://r2.eu.bedrock.engineer/bimpolars/rvt-advanced-sample/rvt-advanced-sample-combined-arch-str-bdf.parquet"
        ).filter(pl.col("class") == "Structural Foundations"),
        site_crs,
    )
    return (foundations_bimdf,)


@app.cell(hide_code=True)
def viewer_controls(
    SBTN_LABELS,
    SOIL_BEHAVIOR_COLORS,
    bim_objects,
    cpts_bimdf,
    foundations_bimdf,
    mo,
    pl,
    volumes_bimdf,
):
    # What the viewer shows. An SBTn in the legend shows or hides its volume; the CPTs' cylinders have the same colors.
    _labels = {_zone: _label for _zone, _label in SBTN_LABELS.items() if _label in volumes_bimdf["name"].to_list()}
    show_foundations = mo.ui.checkbox(value=True, label="Revit foundations")
    show_cpts = mo.ui.checkbox(value=True, label="Interpreted CPTs")
    show_volumes = mo.ui.checkbox(value=True, label="SBTn volumes")
    shown_sbtn = mo.ui.dictionary(
        {
            _label: mo.ui.checkbox(
                value=True,
                label=f'<span style="display: inline-flex; gap: 6px;"><span style="flex: none; width: 12px; height: 12px; margin-top: 4px; background: {SOIL_BEHAVIOR_COLORS[_zone]}; border: 1px solid #bbb;"></span>{_label}</span>',
            )
            for _zone, _label in _labels.items()
        }
    )
    # Laid out here: a cell that references the checkboxes themselves runs again with each click, and the viewer's cell
    # would then build a new viewer and fetch the 3D BAG again
    viewer_controls = mo.vstack(
        [
            mo.md("**Show**"),
            show_foundations,
            show_cpts,
            show_volumes,
            mo.md("**SBTn**"),
            *(shown_sbtn[_label] for _label in _labels.values()),
        ],
        gap=0.25,
    )
    # Each volume, all CPTs and all foundations once as a viewer model, so that showing or hiding one only packs the models again
    volume_models = {_label: bim_objects(volumes_bimdf.filter(pl.col("name") == _label)) for _label in _labels.values()}
    cpt_model = bim_objects(cpts_bimdf)
    foundation_model = bim_objects(foundations_bimdf)
    return (
        cpt_model,
        foundation_model,
        show_cpts,
        show_foundations,
        show_volumes,
        shown_sbtn,
        viewer_controls,
        volume_models,
    )


@app.cell(hide_code=True)
def viewer(
    GeoSpeckleViewer,
    mo,
    pdok_3d_buildings,
    viewer_controls,
    volumes_bimdf,
):
    # One viewer that keeps its 3D BAG when the checkboxes change what it shows
    viewer_widget = GeoSpeckleViewer(tilesets=[pdok_3d_buildings(volumes_bimdf)], height=550)
    bim_viewer = mo.ui.anywidget(viewer_widget)
    mo.hstack([bim_viewer, viewer_controls], widths=[5, 2], align="start")
    return bim_viewer, viewer_widget


@app.cell(hide_code=True)
def viewer_models(
    cpt_model,
    foundation_model,
    models_gz,
    show_cpts,
    show_foundations,
    show_volumes,
    shown_sbtn,
    viewer_widget,
    volume_models,
):
    # Through viewer_widget, not bim_viewer, so that this cell does not run again each time the viewer reports back
    _models = [
        *(_model for _label, _model in volume_models.items() if show_volumes.value and shown_sbtn.value[_label]),
        *([cpt_model] if show_cpts.value else []),
        *([foundation_model] if show_foundations.value else []),
    ]
    viewer_widget.objects_gz = models_gz(*_models) if _models else b""
    return


@app.cell(hide_code=True)
def viewer_selection(
    bim_viewer,
    cpts_bimdf,
    foundations_bimdf,
    mo,
    pl,
    volumes_bimdf,
):
    # The elements selected in the GeoSpeckleViewer, with the statistics of what they merge
    _selected = [_obj["applicationId"] for _obj in bim_viewer.value["selected"]]
    _rows = [
        _frame.filter(pl.col("id").is_in(_selected)).select(
            "id", "name", "class", pl.col("properties").struct.field(_set).struct.unnest()
        )
        for _frame, _set in ((volumes_bimdf, "SBTn volume"), (cpts_bimdf, "CPT"), (foundations_bimdf, "object"))
    ]
    mo.vstack([_row for _row in _rows if _row.height])
    return


@app.cell(hide_code=True)
def publish_intro(mo):
    mo.md(r"""
    ## 4 · Publish to Speckle

    Each BimDataFrame as a new version of a model on a Speckle server, in the site CRS's coordinates, so that the models
    fit together there. Choose a model for each BimDataFrame to publish; one without a model is left out.
    Nothing is sent until **Publish** is pressed.

    The notebook signs in with this machine's Speckle account for the server. Without one, paste a personal access token
    with the scopes `profile:read`, `streams:read` and `streams:write` into the field that appears: it stays in this
    notebook's memory and is never written to disk. Setting `SPECKLE_TOKEN` before starting the notebook fills the field.
    """)
    return


@app.cell(hide_code=True)
def speckle_server_input(DEFAULT_SERVER, mo):
    speckle_server = mo.ui.text(value=DEFAULT_SERVER, label="Server", full_width=True)
    speckle_server
    return (speckle_server,)


@app.cell(hide_code=True)
def speckle_sign_in(EnvConfig, local_client, mo, speckle_server, token_client):
    local_speckle = local_client(speckle_server.value)
    # The field's validator signs in with the token and keeps the client, so the token is sent to the server once
    speckle_signed_in = {}


    def _sign_in(_token):
        speckle_signed_in["client"] = token_client(_token, speckle_server.value)


    speckle_token = mo.ui.anywidget(EnvConfig({"SPECKLE_TOKEN": _sign_in}))
    None if local_speckle else mo.vstack(
        [mo.md(f"No working Speckle account for `{speckle_server.value}` here: paste a token."), speckle_token]
    )
    return local_speckle, speckle_signed_in, speckle_token


@app.cell(hide_code=True)
def speckle_signed_in_as(local_speckle, mo, speckle_signed_in, speckle_token):
    mo.stop(local_speckle is None and not speckle_token.all_valid)
    speckle_client = local_speckle or speckle_signed_in["client"]
    mo.md(
        f"Signed in to `{speckle_client.url}` as **{speckle_client.account.userInfo.name}**, with "
        + ("this machine's account." if local_speckle else "the token.")
    )
    return (speckle_client,)


@app.cell(hide_code=True)
def speckle_targets(
    cpts_bimdf,
    foundations_bimdf,
    mo,
    pl,
    speckle_client,
    volumes_bimdf,
):
    # Speckle only indexes what is under an object's properties for its filters, and a property set's dotted name is
    # its path in the object: the statistics go there, also in the viewer's panel
    speckle_bimdfs = {
        "SBTn volumes": volumes_bimdf.with_columns(
            pl.col("properties").struct.rename_fields(["properties.SBTn volume"])
        ),
        "Interpreted CPTs": cpts_bimdf.with_columns(pl.col("properties").struct.rename_fields(["properties.CPT"])),
        "Revit foundations": foundations_bimdf,
    }
    speckle_project = mo.ui.dropdown(
        {_project.name: _project.id for _project in speckle_client.active_user.get_projects(limit=100).items},
        label="Project",
    )
    speckle_project
    return speckle_bimdfs, speckle_project


@app.cell(hide_code=True)
def speckle_model_choices(
    mo,
    saved_runs,
    speckle_bimdfs,
    speckle_client,
    speckle_project,
):
    mo.stop(speckle_project.value is None, mo.md("Choose a project."))
    _models = {
        _model.name: _model.id
        for _model in speckle_client.model.get_models(speckle_project.value, models_limit=100).items
    }
    speckle_models = mo.ui.dictionary({_label: mo.ui.dropdown(_models, label=_label) for _label in speckle_bimdfs})
    speckle_message = mo.ui.text(
        value=f"SBTn of {saved_runs.value['run'][0]}", label="Message", full_width=True
    )
    publish_button = mo.ui.run_button(label="Publish")
    mo.vstack([*(speckle_models[_label] for _label in speckle_bimdfs), speckle_message, publish_button])
    return publish_button, speckle_message, speckle_models


@app.cell(hide_code=True)
def publish(
    mo,
    publish_button,
    send,
    speckle_bimdfs,
    speckle_client,
    speckle_message,
    speckle_models,
    speckle_project,
):
    mo.stop(not publish_button.value, mo.md("Choose the models to publish to and press **Publish**."))
    _chosen = {_label: _model for _label, _model in speckle_models.value.items() if _model}
    mo.stop(not _chosen, mo.md("Choose at least one model."))
    _project = speckle_project.value
    _published = []
    for _label, _model in mo.status.progress_bar(list(_chosen.items()), title="Publishing"):
        _version = send(speckle_client, speckle_bimdfs[_label], _project, _model, message=speckle_message.value, name=_label)
        _published.append(
            f"- {_label}: [version `{_version}`]({speckle_client.url}/projects/{_project}/models/{_model}@{_version})"
        )
    mo.md("\n".join(_published))
    return


if __name__ == "__main__":
    app.run()
