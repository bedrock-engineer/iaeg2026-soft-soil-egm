# iaeg2026-soft-soil-egm
Open-source soft-soil EGM workflow (GeoTOP, CPTs, GemPy, Speckle) for IAEG 2026.

Project home page with the model extent on a map: <https://bedrock-engineer.github.io/iaeg2026-soft-soil-egm/> (source in [`site/`](site/)).

## Local notebooks

Run `uvx marimo edit --sandbox --watch notebooks/01_get_data.py` to select data around the building footprint loaded from R2. The buffer is measured in RD New metres; touched GeoTOP columns define the exact area used to select CPTs and geotechnical boreholes from the BRO's REST API, by their delivered coordinates. Use the download button to create the local `data/` inputs: `geotop.nc` (all GeoTOP variables), `cpts.parquet` and `selection.json`. The notebook then writes the voxels as a bimpolars BimDataFrame, `geotop_bimdf.parquet`, and shows them in the GeoSpeckleViewer.

Run `uvx marimo edit --sandbox --watch notebooks/02_simulation_domains.py` to group the GeoTOP voxels into simulation domains: start from a preset, assign each GeoTOP unit to a domain, split by lithology or cut the model's base, and compare the domains' CPT coverage and qc/Rf distributions in tables, charts, linked cross-sections and 3D. Saving the domains writes their definition to `notebooks/simulation_domains.json`, which is committed and restored as the notebook's first preset, and the domain of each voxel and CPT sample to `data/voxel_domains.parquet` and `data/sample_domains.parquet` for the next notebook.

Run `uvx marimo edit --sandbox --watch notebooks/03_variograms.py` to fit a variogram per simulation domain to the normal scores of a CPT parameter (log₁₀ qc, log₁₀ fs or Rf), optionally after removing each domain's linear trend with depth: vertically along the CPTs and horizontally between CPTs at one level. Saving writes the variograms, in GSTools' terms, to `notebooks/variograms.json`, which is committed, for the simulation notebook.

Downloaded XMLs, GeoTOP voxels, CPT tables and selection manifests are generated locally and ignored by Git. No data directory is needed in a fresh checkout. The website loads its inputs separately from R2.
