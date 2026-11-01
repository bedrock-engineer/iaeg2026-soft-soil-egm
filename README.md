# iaeg2026-soft-soil-egm
Open-source soft-soil EGM workflow (GeoTOP, CPTs, GemPy, Speckle) for IAEG 2026.

Project home page with the model extent on a map: <https://bedrock-engineer.github.io/iaeg2026-soft-soil-egm/> (source in [`site/`](site/)).

## Local notebooks

Run `uvx marimo edit --sandbox --watch notebooks/01_get_data.py` to select data around the building footprint loaded from R2. The buffer is measured in RD New metres; touched GeoTOP columns define the exact area used to select CPTs and geotechnical boreholes from the BRO PMTiles archive. Use the download button to create the local `data/` inputs.

Downloaded XMLs, GeoTOP voxels, CPT tables and selection manifests are generated locally and ignored by Git. No data directory is needed in a fresh checkout. The website loads its inputs separately from R2.
