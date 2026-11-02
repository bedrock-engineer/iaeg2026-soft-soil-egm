# Amsterdam Noord GeoBIM page

Published at <https://bedrock-engineer.github.io/iaeg2026-soft-soil-egm/>.

The page reuses the actual [bimpolars demo](https://bedrock-engineer.github.io/bimpolars/)
from [specklestuff/site](https://github.com/bedrock-engineer/specklestuff/tree/main/site):
its HTML layout, CSS, draggable 60/40 split, native GeoSpeckleViewer, footprint map,
basemap controls, selection cards, and shift-click selection. The model and intro are
adapted to Amsterdam Noord. BRO location layers are the additional map control.

The browser reads architecture and structure directly from the public model:
<https://r2.eu.bedrock.engineer/bimpolars/rvt-advanced-sample/rvt-advanced-sample-combined-arch-str-bdf.parquet>.
Hyparquet reads the mesh/material columns and decodes the GeoParquet WKB coordinates.
The runtime adapter creates native viewer objects and matching per-element map footprints.
Paired site and geographic vertices recover the ECEF-to-site transform for the
OpenStreetMap ground plane and surrounding PDOK 3D BAG buildings.
The building outline is unioned in RD New meters at 1 mm horizontal precision;
its largest polygon is used for the map outline and hiding overlapping context buildings.
No checked-in model data, generated input geometry files, local data folder, or Python
process is required.

BRO locations load from <https://r2.eu.bedrock.engineer/bro_locations.pmtiles>:
CPT, geotechnical borehole (BHR-GT), and geological borehole (BHR-G) layers, with
visibility toggles, clusters, and hover details. Individual locations appear at zoom 14.

```sh
cd site
npm ci
npm run dev     # http://localhost:5173/iaeg2026-soft-soil-egm/
npm run build   # static site in dist/
```

Internet access and the public services' CORS/range support are required. The native
viewer and page source are vendored under `vendor/geospeckle-viewer` and `src/baseline`
from bedrock-engineer/specklestuff (Apache-2.0; license included). The upstream demo
precomputes viewer traits; `src/baseline/load-model.ts` replaces that pipeline with
browser runtime Parquet loading. `bro-locations.ts` adds the BRO overlay. The rest of
the baseline's interaction and rendering code is retained.

Verification: TypeScript and Vite production build; public Parquet adapter smoke test
(6,355 rows and 6,107 per-element footprints); integrated-browser check of the BIM,
OSM ground, 3D BAG surroundings, BRO map, and linked roof/parapet selection.

`.github/workflows/pages.yml` builds and deploys the site.
