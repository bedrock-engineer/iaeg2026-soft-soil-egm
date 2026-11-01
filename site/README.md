# Project home page

Published with GitHub Pages at <https://bedrock-engineer.github.io/iaeg2026-soft-soil-egm/>.
The compact header, typography and map workspace follow the [bimpolars demo](https://bedrock-engineer.github.io/bimpolars/).

The browser reads the `geog` column directly from the public model:
<https://r2.eu.bedrock.engineer/bimpolars/rvt-advanced-sample/rvt-advanced-sample-combined-arch-str-bdf.parquet>.
Hyparquet uses HTTP range requests and GeoParquet metadata to decode the Polygon Z/MultiPolygon Z WKB.
The architecture and structure footprints are unioned in RD New metres at 1 mm horizontal precision;
the largest polygon becomes the building footprint on the map. No stored or generated geometry files,
root `data/` folder, Python process, or local model cache is needed by this site.

`src/project-geometry.ts` contains the model URL and the 500 × 500 m demo extent/grid settings.
It constructs 25 GeoTOP column footprints in the browser. These are display footprints, not downloaded GeoTOP voxel values.

BRO locations load from <https://r2.eu.bedrock.engineer/bro_locations.pmtiles>:
`cpt`, `bhrgt`, and `bhrg` layers with visibility controls and hover details. CPTs inside the model extent
are highlighted in violet; boreholes remain visible inside and outside the extent.

```sh
npm ci
npm run dev     # http://localhost:5173/iaeg2026-soft-soil-egm/
npm run build   # static site in dist/
```

The model is fetched at runtime; a loading message and retry control handle remote failures.
Internet access and R2's CORS/range support are required for the model, basemaps, and BRO tiles.
The current bimpolars upstream demo precomputes viewer traits at build time; this site reads Parquet
in the browser rather than copying that intermediate-file pipeline.

`.github/workflows/pages.yml` builds and deploys changes to `site/` pushed to `main`.
