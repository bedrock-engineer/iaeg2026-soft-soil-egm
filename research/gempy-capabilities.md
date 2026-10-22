# Can current GemPy build the geology from GeoTOP and run kriging/SGS?

Research for [#3](https://github.com/bedrock-engineer/iaeg2026-soft-soil-egm/issues/3) (parent map [#1](https://github.com/bedrock-engineer/iaeg2026-soft-soil-egm/issues/1)). Researched 2026-10-22.

## Answer

1. **Structural model: yes.** GemPy 2026.0.3 (the v3 line) builds a unit model from GeoTOP if each column's unit bases are used as surface points. A smoke test on synthetic GeoTOP-like columns (5×6 columns of 100 m, 0.5 m voxels, ~500×600×55 m) reproduced the input voxels at 99.4–99.9 % of column-centre cells. A full model computed in about 35 s on CPU.
2. **Geostatistics: yes, but it is no longer in GemPy itself.** The v2 module `gempy.assets.kriging` (used by tutorial `ch3_1`) does not exist in GemPy 2026. It has been replaced by **`gempy_plugins.property_estimation`** (`gempy_plugins` 2026.0.3, released 2026-08-07). That module is a thin wrapper around **GSTools**. It does kriging and conditional simulation per GemPy domain (lithology × fault block), on the GemPy regular grid. It ran end to end in the smoke test.
3. **Caveat on the word "SGS".** GSTools `CondSRF` is *not* sequential Gaussian simulation. It builds `kriged mean + unconditional field × sqrt(kriging variance / sill)` (verified in source). It honours the data and the kriging variance, so it works as a "conditional Gaussian simulation". If the slides say "SGS", either change the wording or use one of the alternatives in §4.
4. **`gempy_probability` does not fit.** It is Bayesian (Pyro) inference of *structural* parameters, not property simulation. Its PyPI release also pins `gempy~=2024.2.0`, and its `main` branch pins `gempy~=2025.1.0`. Both conflict with GemPy 2026.

### Recommendation for a 1-week build

Pin `gempy==2026.0.3`, `gempy_plugins==2026.0.3` and `gstools==1.7.0` (Python 3.12). Then:

- **Notebook A (geology):** GeoTOP voxels → unit-base points per column → GemPy model with 3–5 groups, plus zero-thickness points where a unit is absent (see §2) → `lith_block` on a 10×10×0.5 m grid.
- **Notebook B (parameters):** CPT log(qc) and log(fs), averaged to 0.5 m → `ConditioningData` → for each unit, an anisotropic GSTools variogram (`len_scale=[Lh, Lh, Lv]`) → `run_kriging` (mean and variance) and `run_simulation` with N seeds (realisations, then P10/P50/P90).
- If the plugin gets in the way, drop to plain GSTools with the same objects. The plugin is about 170 lines around `gs.krige.*` and `gs.CondSRF`, and nothing else is needed.
- Call the method "conditional Gaussian simulation (GSTools)". Do not call it SGS unless you implement the conditioning step yourself (§4).

Do not use PyKrige: it has no simulation. Do not use geostatspy: it is the only true 3D SGS, but it is slow pure-Python/numba code, has GSLIB-style parameter lists and no cell mask.

## Sources and how each claim was checked

Legend: **[V]** verified (ran it, or read the installed source). **[D]** read in docs or source online. **[I]** inferred.

`docs.gempy.org`, `gempy.readthedocs.io` and the github.com HTML/API pages were blocked from this sandbox. GemPy claims are therefore based on the **installed package source** (PyPI wheels) and on `raw.githubusercontent.com` files.

| Package | Version (PyPI, 2026-10-22) | Released | Notes |
|---|---|---|---|
| `gempy` | 2026.0.3 (pre-releases up to 2026.2.0a1) | 2026-06-18 | extras: `[base]` adds `gempy_viewer` and pandas; `[opt]` adds `gempy_plugins` and more |
| `gempy_engine` | 2026.0.3.post1 | 2026-06-18 | numpy backend by default, optional torch |
| `gempy_viewer` | 2026.0.5 | 2026-08-07 | pyvista optional |
| `gempy_plugins` | 2026.0.3 | 2026-08-07 | contains `property_estimation`, `orientations_generator`, `topology_analysis` |
| `gempy_probability` | 2024.1.1 | 2024-09-06 | `requires gempy~=2024.2.0`; `main` requires `gempy~=2025.1.0` |
| `gstools` | 1.7.0 | 2025-04-28 | |
| `PyKrige` | 1.7.3 | 2025-10-16 | |
| `geostatspy` | 0.0.79 | 2025-11-07 | |

All of these are **[V]**: PyPI JSON API, and installed into a scratch `uv` venv on Python 3.12.

## 1. What changed between GemPy v2 and v3

- v2 had `gempy/assets/kriging.py`, with classes `domain` and `variogram_model` and functions `create_kriged_field` and `create_gaussian_field`. The tutorial imports it as `from gempy.assets import kriging` and runs `kriging.domain(model=sol, domain=[2], data=cond_data)` followed by `kriging.create_gaussian_field(...)`. Sources: [`v2.3.1/gempy/assets/kriging.py`](https://raw.githubusercontent.com/gempy-project/gempy/v2.3.1/gempy/assets/kriging.py) and [`ch3_1_kriging_interpolation_and_simulation.py`](https://raw.githubusercontent.com/gempy-project/gempy/v2.3.1/examples/tutorials/ch3-Interpolations/ch3_1_kriging_interpolation_and_simulation.py). **[D]**
- GemPy 2026.0.3 has no `assets` package: `gempy/` contains only `API`, `core` and `modules`. Searching the source for `krig` finds only the engine's *universal cokriging of the scalar field* (`interpolate_feature_with_cokrig`), which is the structural interpolator and not a property tool. **[V]**
- `gempy_plugins.property_estimation` is the successor. Its docstring says domains are `(lith_id, fault_block_id)` pairs, *"something the old kriging plugin's lithology-only masking couldn't do"*. It requires `gstools` at runtime (`require_gstools()`). Source: installed wheel, mirrored at [`gempy_plugins/property_estimation`](https://raw.githubusercontent.com/gempy-project/gempy_plugins/main/gempy_plugins/property_estimation/simulation.py). **[V]**

## 2. GeoTOP → GemPy structural model

### Input convention

- In GemPy v3 a structural element's surface points mark its **base**. The element's region lies between the previous element's surface and its own. The basement has no points. Evidence: `structural_elements_from_borehole_set` builds each element's surface points from `borehole_set.get_bottom_coords_for_each_lith()`. In the smoke test, `describe_domains` maps `lith_block` id *i* to the *i*-th element (youngest first), with `basement` last. **[V]**
- At least one orientation is needed per group. A single horizontal one (`G_z=1`) at the centroid is enough for flat-lying Holocene units. **[V]**
- Stacking: `gp.data.StructuralGroup(..., structural_relation=StackRelationType.ERODE | ONLAP | BASEMENT | FAULT)` from `gempy_engine.core.data.stack_relation_type`. **[V]**
- Grid: `gp.create_geomodel(extent=..., resolution=[nx,ny,nz], structural_frame=frame, intpolation_options_tye=InterpolationOptionsType.DENSE_GRID)`. Note the misspelt keyword in the real API. `InterpolationOptionsType` is imported from `gempy.core.data.options` and is *not* re-exported in `gp.data`. **[V]**

### Recommended extraction (per GeoTOP column)

For each 100×100 m column and each strat unit present, take one point at the **bottom face of the lowest voxel** of that unit: `(x_c, y_c, z_min − 0.25)`. A 400×500 m box (plus the extra northern row) gives about 30 columns, so about 30 points per unit. That is plenty for GemPy. CPT-interpreted unit boundaries can be appended as extra points at their true x, y. **[V] for the mechanics; [I] for the CPT addition.**

### Absent and discontinuous units (pinch-outs, palaeochannels)

GemPy has no "absent here" flag. A conformable stack (one scalar field) cannot make a unit vanish; it can only make the unit thin. Smoke-test results for a Basal Peat (NIBA) that is absent in the western columns:

| Setup | NIBA cells where GeoTOP has none | Agreement with voxels |
|---|---|---|
| NIBA in the same conformable group as the Holocene clays (points just omitted where absent) | 1666 | 98.7 % |
| NIBA in its own `ONLAP` group (points omitted where absent) | 921 | 99.4 % |
| NIBA in its own group **plus zero-thickness points**: where it is absent, its base point is placed at the base of the overlying unit | **168** | **99.9 %** |

**[V]**

So:

- Put units that pinch out in their **own group**, and add **zero-thickness points** where GeoTOP has none. Do not use zero-thickness points inside one conformable group: two different scalar values at the same location conflict. **[I]**
- Model erosive bodies, such as palaeochannel fills and the anthropogenic fill, as their own `ERODE` group above what they cut. Their base points come only from the columns where they occur. A channel narrower than a 100 m GeoTOP column cannot be resolved from GeoTOP alone. **[I]**
- Practical rule for one week: **merge GeoTOP units into 4–6 engineering-geological units** before going into GemPy (for example: fill, Holocene clay/peat, Wormer sand/clay, Basal Peat, Pleistocene sand). Keep lithoclass detail as a property and do not use it as structure. **[I]**
- The model has no topography by default, so the top unit fills the air up to `z_max` (visible as an inflated AAOP cell count). Use `gp.set_topography_from_arrays(geo.grid, xyz)` with AHN, or mask cells above ground level afterwards. **[D, signature in `grid_API.py`]**

## 3. Library comparison for property simulation within units

| | **gempy_plugins.property_estimation** | **GSTools 1.7** (direct) | **PyKrige 1.7.3** | **geostatspy 0.0.79** | **gempy_probability** |
|---|---|---|---|---|---|
| Conditioning to data | yes (`ConditioningData`, nearest-cell domain assignment) | yes (`Krige(cond_pos, cond_val)`, `exact`, `cond_err`) | yes (kriging only) | yes | n/a |
| Anisotropic variogram | yes (GSTools `CovModel`, `len_scale=[a,b,c]`, `angles`); anisotropy-aware moving neighbourhood via `model.isometrize` | yes, plus `vario_estimate(direction=…)` and `vario_estimate_axis` | yes (`anisotropy_scaling_y/z`, angles) | yes (`hmaj/hmin/hvert`, azimuth) | n/a |
| Multiple realisations | yes (`seed` per call) | yes | **no simulation** | yes (`nreal`) | n/a (structural) |
| True SGS | no: CondSRF (kriged mean + scaled unconditional field) | no, same mechanism | no | **yes** (GSLIB `sgsim` port, `sgsim_3D`) | no |
| Regular 3D grid masked per unit | **built in** (lith × fault-block domains taken from `geo_model.solutions`) | do it yourself with a numpy mask (`mesh_type="unstructured"` on the cell centres) | do it yourself | no mask: simulates the full box | n/a |
| Normal-score / log transform | through `krige_kwargs={"normalizer": gs.normalizer.LogNormal()}` | `gs.normalizer.*` (LogNormal, BoxCox, YeoJohnson…) | no | yes (`itrans`) | n/a |
| Speed (smoke test, 330 k cells, 960 data) | ~64 s per realisation (all domains); kriging 49 s | same | — | not tested; per-node python/numba loop **[I]** | — |
| Compatible with gempy 2026 | yes | yes | yes | yes | **no** (version pin) |

All rows **[V]** from installed source and signatures, except where marked otherwise.

## 4. Minimal code for each path

### Path A (recommended): GemPy 2026 + gempy_plugins (GSTools)

```python
import numpy as np, gempy as gp, gstools as gs
from gempy.core.data.options import InterpolationOptionsType
from gempy_engine.core.data.stack_relation_type import StackRelationType
from gempy_plugins.property_estimation.conditioning_data import ConditioningData
from gempy_plugins.property_estimation.domains import compute_domains, describe_domains
from gempy_plugins.property_estimation.kriging import KrigingDomainConfig, run_kriging
from gempy_plugins.property_estimation.simulation import SimulationDomainConfig, run_simulation

def element(name, xyz, color):  # xyz = unit-base points from GeoTOP columns (+ zero-thickness points)
    sp = gp.data.SurfacePointsTable.from_arrays(x=xyz[:,0], y=xyz[:,1], z=xyz[:,2], names=name)
    c = xyz.mean(0)
    ori = gp.data.OrientationsTable.from_arrays(x=[c[0]], y=[c[1]], z=[c[2]], G_x=[0], G_y=[0], G_z=[1], names=name)
    return gp.data.StructuralElement(name=name, color=color, surface_points=sp, orientations=ori)

frame = gp.data.StructuralFrame(structural_groups=[
    gp.data.StructuralGroup(name="Fill",      elements=[element("AAOP", p["AAOP"], "#999")], structural_relation=StackRelationType.ERODE),
    gp.data.StructuralGroup(name="Holocene",  elements=[element("NIHO", p["NIHO"], "#6b8e23"), element("NAWO", p["NAWO"], "#4682b4")], structural_relation=StackRelationType.ERODE),
    gp.data.StructuralGroup(name="BasalPeat", elements=[element("NIBA", p["NIBA"], "#8b4513")], structural_relation=StackRelationType.ONLAP),
    gp.data.StructuralGroup(name="Pleist",    elements=[element("BXWI", p["BXWI"], "#daa520")], structural_relation=StackRelationType.ERODE),
], color_gen=gp.data.ColorsGenerator())
geo = gp.create_geomodel(extent=[xmin, xmax, ymin, ymax, -50, 5], resolution=[40, 50, 110],
                         structural_frame=frame, intpolation_options_tye=InterpolationOptionsType.DENSE_GRID)
gp.compute_model(geo)

lith, fault, keys = compute_domains(geo)            # (lith_id, fault_block_id) per cell
cond = ConditioningData(cpt.x, cpt.y, cpt.z, np.log(cpt.qc))   # CPT, averaged to 0.5 m
cond.assign_domains(geo, lith, fault)
model = lambda: gs.Exponential(dim=3, var=0.1, len_scale=[40, 40, 1.5])  # fit per unit in practice
kr = run_kriging(geo, cond, {k: KrigingDomainConfig(model=model()) for k in keys if len(cond.for_domain(k))})
reals = [run_simulation(geo, cond, {k: SimulationDomainConfig(model=model(), seed=s)
                                    for k in keys if len(cond.for_domain(k))}).values
         for s in range(20)]                         # → np.nanpercentile(reals, [10, 50, 90], axis=0)
```

### Path B: plain GSTools on a masked grid (same maths, no plugin)

```python
xyz = geo.grid.regular_grid.values; m = (geo.solutions.raw_arrays.lith_block == unit_id)
model = gs.Exponential(dim=3, var=v, len_scale=[Lh, Lh, Lv])
# variogram fit from CPT data within the unit:
bins, gam = gs.vario_estimate(d.xyz.T, d.values, bin_edges, direction=[[0, 0, 1]], bandwidth=1.0)  # vertical
krige = gs.krige.Ordinary(model, cond_pos=d.xyz.T, cond_val=d.values)
srf = gs.CondSRF(krige)
field = np.full(m.size, np.nan)
field[m] = srf(xyz[m].T, seed=s, mesh_type="unstructured")
```

### Path B′: textbook conditioning by kriging (only if "SGS-equivalent" must hold exactly) [I]

```python
uncond = gs.SRF(model, seed=s)
u_grid = uncond(xyz[m].T, mesh_type="unstructured"); u_data = uncond(d.xyz.T, mesh_type="unstructured")
k_d = gs.krige.Simple(model, d.xyz.T, d.values, mean=mu)(xyz[m].T, mesh_type="unstructured", return_var=False)
k_u = gs.krige.Simple(model, d.xyz.T, u_data, mean=0)(xyz[m].T, mesh_type="unstructured", return_var=False)
field[m] = k_d + (u_grid - k_u)   # exact conditional covariance; not tested here
```

### Path C: PyKrige (kriging only, no simulation)

```python
from pykrige.ok3d import OrdinaryKriging3D
ok = OrdinaryKriging3D(x, y, z, v, variogram_model="exponential", anisotropy_scaling_z=Lh / Lv)
est, var = ok.execute("points", xg[m], yg[m], zg[m])
```

### Path D: geostatspy (true SGS, full box, then mask)

```python
import geostatspy.geostats as geostats
vario = geostats.make_variogram3D(nug=0, nst=1, it1=2, cc1=1, azi1=0, dip1=0, hmaj1=Lh, hmin1=Lh, hvert1=Lv)
sim = geostats.sgsim_3D(df, 'X', 'Y', 'Z', 'logqc', ..., nreal=10, nx=nx, xmn=..., xsiz=10, ny=..., nz=..., zsiz=0.5,
                        seed=73073, ndmin=0, ndmax=20, nodmax=20, mults=0, nmult=2, noct=-1, ktype=0, ..., vario=vario)
sim[:, ~unit_mask.T] = np.nan          # sgsim_3D returns (nreal, nz, ny, nx); run once per unit
```

The geostatspy call signature has 41 positional arguments (`geostats.py` line 6546). It was not run here. **[D]**

## 5. Smoke test

Environment: `uv venv --python 3.12`, then `uv pip install "gempy[base]==2026.0.3" gempy_plugins==2026.0.3 gstools pykrige geostatspy pyvista`. CPU only, numpy backend.

Input: synthetic "GeoTOP" with 5×6 columns at 100 m, 0.5 m voxels, units AAOP / NIHO / NAWO / NIBA / BXWI over a KRZU basement, and NIBA absent in the western 2 columns. Synthetic CPTs: 12 soundings, 0.5 m samples, 960 values of log(qc).

Results:

- Points extracted: 30 per unit (13 for NIBA). `gp.compute_model` on a 50×60×110 grid (10×10×0.5 m, 330 k cells): **35 s**.
- Domains `(1,0)…(6,0)` = AAOP…basement. Agreement between GemPy `lith_block` and the input voxels at column centres: **99.4 %**, or **99.9 %** with zero-thickness points.
- `run_simulation` with an anisotropic Exponential model (`len_scale=[40,40,1.5]`), Simple kriging with the per-unit mean, 3 seeds: **192 s for 3 realisations**. No NaN cells, realisations differ, median |sim − data| at the nearest cell is 0.17 in log-qc (data are not at cell centres).
- `run_kriging` (Ordinary): **49 s**, variance range 0.017–0.117 (sill 0.1).
- **Not tested:** real GeoTOP or BRO data, topography masking, Path B′, geostatspy, GPU or torch backend, and memory at finer grids. Global kriging solves an n×n system per unit. With CPTs averaged to 0.5 m (~100 values per CPT) and 10–30 CPTs, that is ≤3 000 points per unit, which is fine. Raw 2 cm CPT data would need averaging or `Neighborhood("n_closest")`. **[I]**

The smoke script was run from `/tmp/.../scratchpad/smoke/smoke.py`; its full logic is the Path A sketch above, plus the voxel extraction:

```python
for i, j in columns:                       # GeoTOP column (x_c, y_c)
    for u in units:
        idx = np.where(vox[i, j] == u)[0]
        if idx.size: pts[u].append((xc[i], yc[j], zc[idx.min()] - dz / 2))   # base of unit
# zero-thickness: where unit u is absent, put its base at the base of the unit directly above
```

## 6. Open points for the map

- **Variogram inference:** CPTs give good vertical ranges, but 100 m GeoTOP spacing and sparse CPTs give weak horizontal ranges. Expect to *assume* horizontal ranges (tens of metres) or borrow them from literature, and say so on the slides. **[I]**
- **What to simulate:** log(qc) and log(fs) separately (independent), or Rf. Co-simulation is not in GSTools or the plugin. **[I]**
- **Grid for Speckle:** 10×10×0.5 m over 400×600×55 m is about 260–330 k cells. Mean, P10 and P90 are three scalar arrays on the same grid. **[V] for cell count.**
