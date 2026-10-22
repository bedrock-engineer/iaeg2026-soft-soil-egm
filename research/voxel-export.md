# Exporting the voxel parameter model to VTK, netCDF/zarr and Speckle

Research for [#4](https://github.com/bedrock-engineer/iaeg2026-soft-soil-egm/issues/4), part of the map in [#1](https://github.com/bedrock-engineer/iaeg2026-soft-soil-egm/issues/1).
Date: 2026-10-22. Scope: a one-week build for the XV IAEG 2026 demo.

## TL;DR

| Target | Recommendation | Size measured at 10×10×0.5 m (220,000 voxels) |
|---|---|---|
| **VTK** | `pyvista.ImageData` (uniform grid) with values in `cell_data`, saved as XML `.vti` (zlib, the PyVista default). Don't use UnstructuredGrid. | 2.1 MB for 1 realisation, 21 MB for 10 |
| **netCDF / zarr** | One `xarray.Dataset` with dims `(realization, z, y, x)`, cell-centre coordinates, CF-1.11 attributes and a `crs` grid-mapping variable that holds `crs_wkt` for **EPSG:7415** (RD New + NAP height). Write netCDF4 with zlib as the main file; zarr v3 is the same dataset with one extra call. Follow GeoTOP's naming (`x`, `y`, `z`, integer unit codes plus a lookup table), but don't copy its corner-based x/y. | netCDF 1.4 MB (1 real.) / 13.9 MB (10 real.); zarr 1.6 / 15.6 MB |
| **Speckle** | **Don't send one object per voxel at 10 m.** Send two collections: (a) **column runs**, one box `DataObject` for each run of same-unit voxels in an x-y column, with scalar `properties` (unit, top, bottom, thickness, mean qc, mean fs); (b) **one merged boundary mesh per unit** for a fast overview. Colour both with the existing `colorProxies`. Send only a summary realisation. Keep the proven `operations.send` path; trying `send3` (the parquet bundle) is a stretch goal. | runs: 13,445 objects (40k JSON objects, 26 MB); unit meshes: 7 objects, 155k triangles. Per-voxel for comparison: 660k JSON objects, 411 MB |

## Model dimensions

Box: 400 × 500 × 55 m, with z running from +5 to −50 m NAP.

| Grid | nx × ny × nz | Voxels | × 10 realisations |
|---|---|---|---|
| 25 × 25 × 0.5 m | 16 × 20 × 110 | 35,200 | 352,000 |
| 10 × 10 × 0.5 m | 40 × 50 × 110 | 220,000 | 2,200,000 |

## Method

A scratch uv venv held pyvista 0.49.1, xarray 2026.9.0, zarr 3.4.1, netCDF4 1.7.5, specklepy 2026.9.1 and pyarrow. I generated a synthetic model with seven layered units (fill, Holocene peat/clay, Wormer, basal peat, Boxtel sand, Eem clay, Drente sand). The unit interfaces undulate, and each voxel carries `uint8` unit, `float32` qc and `float32` fs. The scripts are `bench.py` and `speckle_bench.py` in the session scratchpad. They are not committed and can be reproduced from the descriptions below.

Caveats:
- The synthetic qc/fs fields carry lognormal voxel-scale noise, so they compress worse than a smooth kriged field. Treat the compressed sizes as **upper bounds**.
- Nothing was sent to a Speckle server. Speckle numbers come from serialising locally:
  - for the JSON path, through `operations.send` into a `MemoryTransport`;
  - for the parquet path, through `BundleBuilder.build()`.

---

## 1. VTK

### Structure

- The model is an axis-aligned regular grid in RD New, so **`pyvista.ImageData`** is the right type.
  - It stores only `origin`, `spacing` and `dimensions`, plus the arrays.
  - `ImageData` has supported a `direction_matrix` since VTK 9.2 (see the `pyvista/core/grid.py` docstring), but we don't need rotation.
- Voxel values belong in **`cell_data`**, with `dimensions = (nx+1, ny+1, nz+1)` points. Putting them in `point_data` would turn every voxel into a point and make ParaView interpolate between them.
- `RectilinearGrid` gives identical size here (2.07 MB). It only adds value if dz varies with depth.
- `UnstructuredGrid` is 2.9× larger at 1 realisation (5.9 MB) and gives no benefit. Use it only for a clipped, non-box domain, and even then thresholding an `ImageData` in ParaView is easier.
- `PyVista DataObject.save(..., compression='zlib')` is the default (`pyvista/core/dataobject.py`). The extension picks the writer: `.vti`, `.vtr`, `.vtu`, `.vtk`, `.vtkhdf`.

Measured sizes:

| File | 25 m, 1 real. | 10 m, 1 real. | 10 m, 10 real. |
|---|---|---|---|
| `.vti` (XML, zlib) | 0.33 MB | 2.07 MB | 20.7 MB |
| `.vti` (no compression) | 0.42 MB | 2.64 MB | 26.4 MB |
| `.vtr` | 0.33 MB | 2.07 MB | 20.7 MB |
| `.vtu` | 0.99 MB | 5.94 MB | 24.5 MB |
| legacy `.vtk` (binary) | 0.32 MB | 1.98 MB | 19.8 MB |

Every write took under 1.2 s.

### Realisations in VTK

VTK has no "realisation" dimension. Two options:
- Store per-realisation arrays (`unit_r00`, `qc_r00`, …) next to summary arrays: most-probable unit, unit probability, qc P10/P50/P90.
- Write one `.vti` per realisation.

At 10 m, ten realisations come to only about 21 MB, so a single file with suffixed arrays is fine. ParaView users colour by the summary arrays first.

VTK has no CRS slot. Put the CRS and unit lookup in `field_data`, as in the sketch below. RD coordinates (~1.2e5 m) work fine at float64 in ParaView.

```python
import numpy as np, pyvista as pv
grid = pv.ImageData(dimensions=(nx+1, ny+1, nz+1), spacing=(dx, dy, 0.5),
                    origin=(x_min, y_min, z_min_nap))          # corners, not centres
# arrays are (nx, ny, nz) -> VTK wants x fastest: ravel(order="F")
grid.cell_data["unit"]   = unit.ravel(order="F").astype(np.uint8)
grid.cell_data["qc_MPa"] = qc.ravel(order="F").astype(np.float32)
grid.cell_data["fs_MPa"] = fs.ravel(order="F").astype(np.float32)
grid.field_data["unit_codes"] = np.array(unit_names)            # index -> name
grid.field_data["crs"] = np.array(["EPSG:7415 (Amersfoort / RD New + NAP height)"])
grid.save("egm_voxels.vti")                                      # zlib by default
```

Going the other way, from the xarray Dataset in section 2, is a few lines: `ds[v].transpose("x","y","z").values.ravel(order="F")`.

---

## 2. netCDF / zarr

### What the sources say

- **CF grid mapping** (CF 1.11 §5.6, `ch05.adoc`). A data variable points to a grid-mapping variable through its `grid_mapping` attribute. That variable may hold `crs_wkt`, which "should comprise a text string that conforms to the WKT syntax".
- **RD New has no CF `grid_mapping_name`.** CF Appendix F only has `stereographic`, which maps to PROJ `stere`. RD New uses the *double* oblique stereographic, PROJ `sterea` / EPSG method 9809. This is why `pyproj.CRS.from_epsg(28992).to_cf()` returns only `crs_wkt`. For EPSG:7415, `to_cf()` returns a COMPOUNDCRS `crs_wkt` plus `geopotential_datum_name = "Normaal Amsterdams Peil"`.
  - Use `crs_wkt` and also set `spatial_ref` (the same WKT) so that GDAL and rioxarray pick it up.
- **Projected coordinates** use `standard_name = projection_x_coordinate` / `projection_y_coordinate` (CF §5.6 / App. F).
- **Vertical coordinate.** It needs a `positive` attribute, `up` or `down` (CF §4.3). Use `z` with `units="m"` and `positive="up"`, and say "height above NAP" in `long_name`. The datum itself is carried by the compound WKT.
- **Cell extents.** Without `bounds`, "an application can make no assumption about the location or extent of the cells" (CF §7.1). Add `x_bnds`, `y_bnds` and `z_bnds`.
- **Categorical unit.** Use `flag_values` + `flag_meanings` (CF §3.5) for the integer unit code, and keep a separate lookup table (code, name, colour) as an attribute or a small side variable.
- **Realisations.** The CF standard-name table has `realization`: "used to label a dimension that can be thought of as a statistical sample, e.g., labelling members of a model ensemble". Make it the leading dimension.

### GeoTOP's own layout

DINOloket serves GeoTOP as one netCDF over OPeNDAP at `https://www.dinodata.nl/opendap/GeoTOP/geotop.nc`. I couldn't fetch the header directly because dinodata.nl was blocked from this sandbox. The layout below is taken from the readers that open that file: `nlmod.read.geotop.download_geotop` (nlmod 0.11.2) and `bromodels.GTM.GeoTop`.

- Dimensions are stored as `(x, y, z)`. nlmod transposes them to `(z, y, x)` and flips z and y.
- Variables:
  - `strat`: the stratigraphic unit, an integer code that maps to `STR_UNIT_CD`.
  - `lithok`: the lithoclass.
  - `kans_1` … `kans_9`: the probability of each lithoclass.
  - `onz_lk` and `onz_ls`: uncertainty in lithoclass and in strat.
- Voxels are 100 × 100 × 0.5 m.
- `z` is the voxel **centre**. nlmod builds top and bottom as `z ± 0.25`.
- **x and y are cell corners.** nlmod's comment says "set x and y dimensions to cell center", and it shifts the stored values by `dx/2`.

So our file can mirror GeoTOP's vocabulary. Use the dimension names `x`/`y`/`z`, z as the centre in m NAP, and integer codes with a lookup table. Where it fits, borrow GeoTOP's realisation-summary idea: a most-probable unit plus a probability per class, like `kans_*`, and an uncertainty measure, like `onz_*`.

Don't copy the corner-referenced x/y. Use cell centres plus `*_bnds`, which is what CF expects. Order the dimensions `(realization, z, y, x)`, the usual CF/COARDS order and nlmod's working order.

> **Side finding (existing notebook).** `amsterdam_noord_geotop_to_speckle.py` builds each GeoTOP box as `x ± 50, y ± 50` around the coordinates that bromodels returns. bromodels does *not* apply nlmod's half-cell shift. If nlmod is right that the stored x/y are corners, the Speckle voxels sit 50 m south-west of their true position. This needs a quick check against a known GeoTOP column.

### Measured sizes

netCDF4 used zlib level 4 with shuffle. netCDF4-python picked chunks of `[1, 110, 50, 40]`, one chunk per realisation. zarr v3 used xarray/zarr defaults.

| | 25 m, 1 real. | 10 m, 1 real. | 10 m, 10 real. |
|---|---|---|---|
| raw in memory | 0.32 MB | 1.98 MB | 19.8 MB |
| netCDF4 uncompressed | 0.34 MB | 2.00 MB | 19.8 MB |
| **netCDF4 zlib 4** | 0.26 MB | 1.42 MB | 13.9 MB |
| zarr v3 (default codec) | 0.27 MB (15 files) | 1.57 MB (21 files) | 15.6 MB (53 files) |

All writes took under 1 s. Size doesn't decide anything here. Readers do:
- **netCDF4** opens in QGIS (GDAL), Panoply and ParaView (it has a CF netCDF reader), and travels as a single file.
- **zarr** is a directory of chunk files. It pays off for cloud or HTTP range access, for example from a web viewer.

Write netCDF as the deliverable. Add `ds.to_zarr(...)` only if the web demo needs it.

```python
import numpy as np, pyproj, xarray as xr
cf = pyproj.CRS.from_epsg(7415).to_cf()            # {'crs_wkt': 'COMPOUNDCRS[...]', 'geopotential_datum_name': 'Normaal Amsterdams Peil'}
cf["spatial_ref"] = cf["crs_wkt"]                  # GDAL / rioxarray
codes = np.arange(len(unit_names), dtype=np.uint8)
ds = xr.Dataset(
    data_vars={
        "unit": (("realization", "z", "y", "x"), unit_rzyx, {
            "long_name": "geological unit", "flag_values": codes,
            "flag_meanings": " ".join(unit_names), "grid_mapping": "crs"}),
        "qc": (("realization", "z", "y", "x"), qc_rzyx, {
            "long_name": "interpolated CPT cone resistance", "units": "MPa", "grid_mapping": "crs"}),
        "fs": (("realization", "z", "y", "x"), fs_rzyx, {
            "long_name": "interpolated CPT sleeve friction", "units": "MPa", "grid_mapping": "crs"}),
        "crs": ((), np.int32(0), cf),
    },
    coords={
        "realization": ("realization", np.arange(n_real), {"standard_name": "realization"}),
        "x": ("x", xc, {"standard_name": "projection_x_coordinate", "units": "m", "axis": "X", "bounds": "x_bnds"}),
        "y": ("y", yc, {"standard_name": "projection_y_coordinate", "units": "m", "axis": "Y", "bounds": "y_bnds"}),
        "z": ("z", zc, {"standard_name": "height", "long_name": "height of voxel centre above NAP",
                        "units": "m", "positive": "up", "axis": "Z", "bounds": "z_bnds"}),
        "x_bnds": (("x", "nv"), np.c_[xc - dx/2, xc + dx/2]),
        "y_bnds": (("y", "nv"), np.c_[yc - dy/2, yc + dy/2]),
        "z_bnds": (("z", "nv"), np.c_[zc - 0.25, zc + 0.25]),
    },
    attrs={"Conventions": "CF-1.11", "title": "Amsterdam soft-soil EGM voxel model",
           "source": "GeoTOP + BRO CPTs, <method>", "references": "https://github.com/bedrock-engineer/iaeg2026-soft-soil-egm"},
)
enc = {v: {"zlib": True, "complevel": 4} for v in ("unit", "qc", "fs")}
ds.to_netcdf("egm_voxels.nc", encoding=enc)       # main deliverable
ds.to_zarr("egm_voxels.zarr", mode="w", zarr_format=3, consolidated=True)  # optional
```

---

## 3. Speckle

### How properties become filters

Primary source: `specklepy/bundle/eav_extraction.py` in specklepy 2026.9.1. Its docstring calls it a port of the .NET SDK's `EavExtraction.cs`, "itself a port of the server's `packages/shared/src/filtering/eavExtraction.ts`". This is the code that builds the filterable attribute table.

- Only these are indexed:
  - the dict under **`properties`**, walked as `properties.<key>[.<subkey>…]` up to `MAX_DEPTH = 10`;
  - a fixed set of root scalars: `name`, `type`, `family`, `category`, `level`, `units`, `speckle_type`, `applicationId`, … .
- **Scalars only.** Values that are lists or arrays are skipped ("non-scalar, non-dict … skipped"). Don't put arrays such as a qc profile in `properties`.
- A dict shaped like **`{"name": …, "value": …, "units": …}`** becomes one row that carries its **units**. Use this shape for qc, fs and thickness.
- The type is inferred:
  - Python int and float become `number`, which gives numeric range filters.
  - `"true"`/`"false"` become `boolean`.
  - Numeric-looking strings also become numbers, unless they look like UUIDs.
  - Units are therefore safest as real floats.
- Nesting is fine. Keep it shallow anyway, for example `properties = {"geological_unit": "NAWO", "qc": {"name": "qc", "value": 1.2, "units": "MPa"}}`.

The existing notebook already does this right: it uses `DataObject(name=…, properties={…}, displayValue=[Mesh])`.

On receive in BIM tools, properties survive as follows:
- **Rhino** flattens the `properties` dict into object **user strings** (`RhinoArtefactUserStrings.cs`, `AttributeExtensions.FlattenDictionaryToUserStrings` in `speckle-sharp-connectors`).
- **Revit** turns DataObjects with mesh `displayValue` into **DirectShapes** (`RevitHostObjectBuilder` / `DirectShapeUnpackStrategy`).

So per-object scalar properties reach Rhino and Revit.

### Viewer limits, from source

Primary source: `packages/viewer/src/modules/batching/Batcher.ts` in speckle-server main.

- Meshes are batched per material, with `maxBatchVertices = 500000`.
- Mesh batches are also capped at `maxBatchObjects = floor((maxVertexUniforms − 33) / 4)`. The 33 comes from `Materials.UNIFORM_VECTORS_USED`.
  - Desktop WebGL usually reports `maxVertexUniforms` = 4096, which gives ~1,015 objects per batch.
  - At 1024, common on mobile and integrated GPUs, it gives ~247.
- Each batch is at least one draw call and one GPU buffer set.
- **Rough draw-batch counts** (objects ÷ objects per batch; the vertex cap is never the binding limit):

  | | 4096 uniforms | 1024 uniforms |
  |---|---|---|
  | per-voxel, 10 m (220k objects) | ~220 | ~890 |
  | per-voxel, 25 m (35k objects) | ~35 | ~140 |
  | column runs, 10 m (13.4k) | ~14 | ~55 |
  | unit meshes (7 objects) | 1 per unit | 1 per unit |

- Every object is also a node in the viewer's world tree and in the filter index. Interactive filtering slows in step with the object count.
- Hardware instancing only kicks in for instance geometry of at least `minInstancedBatchVertices = 10000` vertices. An 8-vertex voxel box is never GPU-instanced, so it is baked per object.

### Measured Speckle payloads (local serialisation, realisation 0)

| Representation | Objects (input) | JSON path: `operations.send` → Speckle objects / bytes | Parquet bundle path: `BundleBuilder.build()` |
|---|---|---|---|
| **per voxel** (existing notebook pattern), 25 m | 35,200 | 105,603 objects / **65.6 MB**, 13 s | 4.4 MB (2.6 MB with an instanced unit box) |
| **per voxel**, 10 m | 220,000 | 660,003 objects / **411 MB**, 87 s | 27 MB (16 MB instanced), 17–25 s |
| **column runs**, 25 m | 2,157 | 6,474 objects / 4.2 MB, 1 s | 0.29 MB |
| **column runs**, 10 m | 13,445 | 40,338 objects / 26 MB, 5 s | 1.7 MB |
| **one boundary mesh per unit**, 10 m | 7 (155k triangles total; largest unit 31k triangles, 15k vertices) | not measured | 1.0 MB |

How to read the table:
- In the JSON path each voxel costs three objects: the `DataObject`, the detached `Mesh` and the detached `vertices` chunk. The `faces` chunk is identical for every box, so it is hashed once and deduplicated.
- Speckle's server batch sender uses 1 MB / 20,000-object batches (`transports/server/batch_sender.py`). That puts the 10 m per-voxel case at roughly 400+ upload requests.

**Verdict on the current approach.** One mesh per voxel works at GeoTOP resolution (100 × 100 m, a few thousand voxels) and is borderline at 25 m (35k objects, 66 MB). At 10 m it isn't viable for a live demo: 411 MB of JSON, 660k objects, hundreds of draw batches and a sluggish filter panel.

### Better options

1. **Column runs (recommended main layer).** In each x-y column, merge contiguous voxels of the same unit into one box `DataObject`.
   - Properties: `geological_unit`, `top_NAP`, `bottom_NAP`, `thickness` (m), `qc_mean`, `fs_mean` (MPa). Optionally add `qc_p10`/`qc_p90` or `unit_probability`.
   - That is 16× fewer objects than per-voxel at 10 m, and each is still a meaningful selectable "layer in a column", which matches how engineers read CPT-based models.
   - Filtering by unit or a qc range then hides or isolates whole layer pieces.
   - Caveat: qc variation inside a run is averaged. Keep full resolution in the VTK/netCDF files.
2. **One boundary mesh per unit (recommended overview layer).** Extract each unit's cells, keep the exterior surface, then triangulate.
   - 7 objects, 155k triangles at 10 m. Fast to load, and every unit is one object for "isolate unit".
   - Properties are unit-level (volume, median qc).
   - Optionally use vertex `colors` on the mesh to show qc. That gives a colour map, not a filter.
3. **Isosurfaces** of qc, for example `grid.cell_data_to_point_data().contour([0.5, 2.0])`, can be added as separate meshes for presentation slides. They aren't needed for filtering.
4. **Point cloud: no.** specklepy's `PointCloud` holds `points: List[Point]` and has no per-point colour or properties (the source comment says "sizes and colors could be added in the future"). It can't carry voxel attributes into filters.
5. **Per-voxel at 25 m** stays an option if the demo specifically needs "click any voxel". It costs 66 MB JSON or 4.4 MB as a bundle. Send it as its own model so the main model stays light.

Realisations: send **one** summary realisation to Speckle: the most-probable unit and qc P50, with an uncertainty property per run such as `unit_probability` or `qc_p90_minus_p10`. The full ensemble lives in netCDF.

### JSON send vs parquet bundle (send3)

- specklepy 2026.9 marks `operations.send` / `serialize` as **deprecated**: "Since 2026.9 – JSON based send/receive pipelines are deprecated and replaced by the parquet bundle pipeline. See operations.send3" (`specklepy/serialization/__init__.py`).
- The new `BundleBuilder` → `operations.send3` path writes parquet tables (EAV properties, envelope, SGEO geometries). Locally it came out **~15× smaller** than JSON for the same per-voxel model. The Revit connector already has a "Speckle 4.0 artefact receive" for these bundles (`RevitConnectorModule.cs`).
- It is weeks old. Its docs link points at `docs.speckle.systems/next`. I couldn't verify against a server that the production `app.speckle.systems` workspace ingests bundles.
- **For a 1-week build:** keep the proven JSON `operations.send` from the existing notebook, which still works and only warns. Use column runs plus unit meshes, which keeps it at about 40k objects and 27 MB. Try `send3` as a stretch goal on a scratch model.

### Code sketch (JSON path, column runs + unit meshes)

```python
import numpy as np
from specklepy.objects import data_objects as sdo, geometry as sg
from specklepy.objects.models.collections.collection import Collection
from specklepy.objects.proxies import ColorProxy, RenderMaterialProxy
from specklepy.objects.other import RenderMaterial

BOX_FACES = [4,0,3,2,1, 4,4,5,6,7, 4,0,1,5,4, 4,1,2,6,5, 4,2,3,7,6, 4,3,0,4,7]  # 6 quads

def box(x0, x1, y0, y1, z0, z1):
    return [x0,y0,z0, x1,y0,z0, x1,y1,z0, x0,y1,z0, x0,y0,z1, x1,y0,z1, x1,y1,z1, x0,y1,z1]

def q(name, value, units):                 # -> one filter row with units
    return {"name": name, "value": float(value), "units": units}

runs, members = [], {u: [] for u in range(len(unit_names))}
for i, j in np.ndindex(nx, ny):
    col = unit[i, j]                                         # (nz,) bottom -> top
    starts = np.flatnonzero(np.r_[True, col[1:] != col[:-1]])
    for s, e in zip(starts, np.r_[starts[1:], nz]):
        u = int(col[s]); bot, top = zc[s] - 0.25, zc[e-1] + 0.25
        aid = f"run_{i}_{j}_{s}"
        runs.append(sdo.DataObject(
            applicationId=aid, name=unit_names[u],
            properties={"geological_unit": unit_names[u],
                        "top_NAP": q("top_NAP", top, "m"), "bottom_NAP": q("bottom_NAP", bot, "m"),
                        "thickness": q("thickness", top - bot, "m"),
                        "qc_mean": q("qc_mean", qc[i, j, s:e].mean(), "MPa"),
                        "fs_mean": q("fs_mean", fs[i, j, s:e].mean(), "MPa")},
            displayValue=[sg.Mesh(vertices=box(xc[i]-dx/2, xc[i]+dx/2, yc[j]-dy/2, yc[j]+dy/2, bot, top),
                                  faces=BOX_FACES, units="m")]))
        members[u].append(aid)

root = Collection(name="EGM", elements=[Collection(name="column runs", elements=runs),
                                         Collection(name="unit envelopes", elements=unit_mesh_objects)])
root["colorProxies"] = [ColorProxy(name=n, value=argb[u], objects=members[u] + [f"unit_{n}"])
                        for u, n in enumerate(unit_names)]
root["renderMaterialProxies"] = [RenderMaterialProxy(value=RenderMaterial(name=n, diffuse=argb[u]),
                                 objects=members[u] + [f"unit_{n}"]) for u, n in enumerate(unit_names)]
# then: operations.send(root, [ServerTransport(...)]) + client.version.create(...) as in the existing notebook
```

The unit envelope meshes come from pyvista:

```python
sub  = grid.extract_cells(np.flatnonzero(grid.cell_data["unit"] == u))
surf = sub.extract_surface(algorithm=None).triangulate().clean()
mesh = sg.Mesh(vertices=surf.points.ravel().tolist(),
               faces=np.c_[np.full(surf.n_cells, 3), surf.regular_faces].ravel().tolist(), units="m")
```

> **Side finding (existing notebook).** The face list in `amsterdam_noord_geotop_to_speckle.py` is
> `[4,0,1,2,3, 4,4,5,6,7, 4,0,1,5,4, 4,2,3,7,6, 4,0,4,5,1, 4,2,6,5,1]`. Face 5 (`0,4,5,1`) is the y-min face again, reversed, and the x-min face (`0,3,7,4`) is missing. So every voxel has one open side and one double face. `BOX_FACES` above is a corrected, consistently outward-wound list.

Geo-referencing in Speckle: send real RD coordinates in metres, as the notebook does. Speckle's viewer handles large coordinates with relative-to-eye rendering (the "RTE" in `Batcher.ts`). Record `EPSG:7415` in a root-level property so that downstream tools know the CRS.

---

## Recommendation for the 1-week build

1. **One canonical in-memory model**: an xarray `Dataset` as in section 2. Every export derives from it.
2. **netCDF4** (zlib 4, CF-1.11, `crs_wkt` for EPSG:7415, centres plus bounds, a `realization` dim): main archival and exchange file, ~14 MB for 10 realisations at 10 m. **zarr** is optional, one line, only if the web viewer needs it.
3. **VTK `.vti`** from `pyvista.ImageData`, values in cell data, summary arrays plus per-realisation arrays: ~2 MB per realisation at 10 m. This is for ParaView figures.
4. **Speckle**: one summary realisation as column-run DataObjects (~13k objects at 10 m) plus 7 unit envelope meshes, with scalar `{name, value, units}` properties and colour/material proxies. Fix the notebook's face list and check the GeoTOP half-cell offset. Stay on JSON `operations.send`; treat `send3` bundles as a stretch goal.
5. **Don't build**: an UnstructuredGrid export, per-voxel Speckle at 10 m, or Speckle point clouds.

## Sources

- PyVista 0.49.1 source: `pyvista/core/dataobject.py` (`save`, default `compression='zlib'`), `pyvista/core/grid.py` (`ImageData`, `direction_matrix`).
- CF Conventions source (github.com/cf-convention/cf-conventions, `main`): `ch03.adoc` (flags), `ch04.adoc` (vertical `positive`), `ch05.adoc` (grid mappings, `crs_wkt`), `ch07.adoc` (cell `bounds`), `appf.adoc` (grid mapping names; only `stereographic`, no oblique/double stereographic). CF standard name table: `realization`.
- pyproj `CRS.to_cf()` output for EPSG:28992 and EPSG:7415, run locally.
- GeoTOP netCDF layout: nlmod 0.11.2 `nlmod/read/geotop.py` (`download_geotop`, `add_top_and_botm`); bromodels `GTM/GeoTop.py`. OPeNDAP URL `https://www.dinodata.nl/opendap/GeoTOP/geotop.nc`; the file header itself wasn't reachable from the sandbox.
- specklepy 2026.9.1 source:
  - `objects/data_objects.py` (`DataObject`)
  - `objects/geometry/mesh.py` (chunkable vertices 31,250 / faces 62,500)
  - `objects/geometry/point_cloud.py`
  - `bundle/eav_extraction.py` (filter property extraction, a port of the server's `eavExtraction.ts`)
  - `bundle/builder.py`, `bundle/sgeo.py`
  - `serialization/__init__.py` (JSON deprecation)
  - `transports/server/batch_sender.py`
- speckle-server `packages/viewer/src/modules/batching/Batcher.ts` and `materials/Materials.ts` (`UNIFORM_VECTORS_USED = 33`).
- speckle-sharp-connectors: Rhino `RhinoArtefactUserStrings.cs`, `Extensions/AttributeExtensions.cs`; Revit `RevitHostObjectBuilder.cs`, `DirectShapeUnpackStrategy.cs`, `RevitConnectorModule.cs`.
- Existing code: `bedrock-experiments/nl_amsterdam/notebooks/amsterdam_noord_geotop_to_speckle.py`, `bedrock-experiments/speckle/`.

Not reachable from this sandbox (blocked by the egress proxy), so not used: docs.speckle.systems, speckle.community, docs.pyvista.org, cfconventions.org, dinodata.nl.
