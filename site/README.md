# Soft Soil EGM, Amsterdam Noord: the GitHub Page

Published at <https://bedrock-engineer.github.io/iaeg2026-soft-soil-egm/>.

The page follows `notebooks/amsterdam_noord_geobim.py` from top to bottom: the GeoSpeckleViewer with
the building on its soft-soil engineering geological model, the CrossSections widget through the
model's cells, and the profile of the selected CPT. Everything is read in the browser from public
Cloudflare R2: no checked-in data, generated input files or Python process.

It reuses the actual [bimpolars demo](https://bedrock-engineer.github.io/bimpolars/)
from [specklestuff/site](https://github.com/bedrock-engineer/specklestuff/tree/main/site):
its HTML layout, CSS, draggable 60/40 split, native GeoSpeckleViewer, footprint map,
basemap controls, selection cards, and shift-click selection. The model and intro are
adapted to Amsterdam Noord. BRO location layers are the additional map control.

## The viewer

The browser reads architecture and structure directly from the public model:
<https://r2.eu.bedrock.engineer/nl-amsterdam-noord/rvt_advanced_sample_combined_arch_str.parquet>,
and beside it the soil's BimDataFrames from <https://r2.eu.bedrock.engineer/nl-amsterdam-noord/>:
`cpts_interpreted_25cm.parquet` (a cylinder per CPT layer) and `sbtn_volumes_25cm.parquet` (a volume
per most likely SBTn zone). Hyparquet reads the mesh/material columns and decodes the GeoParquet WKB
coordinates. The runtime adapter creates native viewer objects, one model each, and matching
per-element map footprints.

Each frame's CRS is a site grid on RD New + NAP. The building is published in the soil's ("GeoTOP
georeferenced BIM CRS", meters, z in m NAP); `src/site-crs.ts` reads the affine transformation and
vertical offset from each frame's `bim_crs` PROJJSON and moves the soil into the building's CRS
whatever it is, as `bpl.to_crs(frame, building.crs)` does in the notebook (an earlier building CRS
was in millimeters and turned). Paired site and geographic vertices recover
the ECEF-to-site transform for the OpenStreetMap ground plane and surrounding PDOK 3D BAG buildings,
which cover the volumes' extent.
The building outline is unioned in RD New meters at 1 mm horizontal precision;
its largest polygon is used for the map outline, hiding overlapping context buildings, and the
footprint in the cross sections.

Over the viewer's top left corner are the notebook's checkboxes, open side by side and folded to
"Layers" on a phone: the ground map and 3D BAG, the architecture,
structure, interpreted CPTs and SBTn volumes, and each kept zone's volume. The models stay loaded:
their elements hide with the viewer's FilteringExtension, so the camera keeps its place, and the
ground map and tilesets are traits of their own, so toggling them sends no models again.
`vendor/geospeckle-viewer` differs from upstream in one place for this: `mountGeoSpeckleViewer`
also returns the Speckle viewer. Selecting a CPT layer or volume shows its property set's
statistics on the card.

## The cross sections and the CPT plot

`notebooks/cross_sections.js`, the notebooks' anywidget, renders on a StaticModel as the viewer
does (`src/cross-sections.ts`), with the traits the GeoBIM notebook sets
(`src/cross-section-traits.ts`) and a Color by choice above it. The cells are read with zarrita from
`soil_model.zarr`, group `25cm`, by name: the grid's int8 arrays first, and each float array when a
mode needs it. The probabilities (16 MB decoded) load after the first paint.

`src/robertson.ts` ports `robertson` from `notebooks/cpt_robertson_classification.py` step for
step, and `src/cpt-samples.ts` the CPT samples of `03_variograms.py` and their classification in
`06_bimdataframes.py`, from `cpts.parquet`. Their `voxel_z` rounds halves to even, as polars'
`round()` does: that is what gives the notebooks' 8,961 samples and 8,901 usable ones. The plot under
the sections (`src/cpt-plot.ts`) is the notebook's Altair chart as a Vega-Lite spec; Vega loads
with it. It follows the CPT clicked in the plan.

SBTn zones 1, 8 and 9 hardly occur and are left out everywhere: volumes, CPT layers, cells,
legends and CPT samples.

## Layouts

Side by side, the viewer and the MapLibre map fill the screen under the bar, and the page scrolls
on to the sections and the plot. Stacked, below 900 px, there is no map: MapLibre is neither loaded
nor started and no map tiles are fetched; the strip on the right scrolls the page beside the
viewer and the sections, whose canvases keep their touches. Narrower than 560 px, the cross sections
lay out compactly (thinner sections, their text under the canvas); notebooks keep their layout.

BRO locations load from <https://r2.eu.bedrock.engineer/bro_locations.pmtiles>:
CPT, geotechnical borehole (BHR-GT), and geological borehole (BHR-G) layers, with
visibility toggles, clusters, and hover details. Individual locations appear at zoom 14.

```sh
cd site
npm ci
npm run dev     # http://localhost:5173/iaeg2026-soft-soil-egm/
npm run build   # static site in dist/
npm run check   # the samples, zones, CRSs and the sections' start against the notebooks' numbers
```

Internet access and the public services' CORS/range support are required (`npm run check` too:
behind a proxy, Node 22 needs `NODE_USE_ENV_PROXY=1`). The native viewer and page source are
vendored under `vendor/geospeckle-viewer` and `src/baseline` from bedrock-engineer/specklestuff
(Apache-2.0; license included). The upstream demo precomputes viewer traits;
`src/baseline/load-model.ts` replaces that pipeline with browser runtime Parquet loading.
`bro-locations.ts` adds the BRO overlay. The rest of the baseline's interaction and rendering code
is retained.

`npm run check` checks, from R2: the building and the volumes line up in one CRS; 8,961 samples,
8,901 usable; 33 samples whose zone differs from their layer in `cpts_interpreted_25cm.parquet`, all
in column x 121,900, y 488,500, where the grid gives a lower ground than GeoTOP (accepted, see
`src/cpt-samples.ts`); 392,743 cells of the kept zones; and the sections' start at x 122,080,
y 488,750, z −14.125 with CPT000000198164.

`.github/workflows/pages.yml` builds and deploys the site.
