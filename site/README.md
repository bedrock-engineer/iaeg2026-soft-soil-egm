# Project home page

The home page of this repo, published with GitHub Pages at
<https://bedrock-engineer.github.io/iaeg2026-soft-soil-egm/>.

It shows the GeoTOP model extent, the fictitious site plot and the BRO CPTs
inside the extent on a MapLibre map. The map is ported from
[bro-xml-app](https://github.com/bedrock-engineer/bro-xml-app)
(`app/components/map/`): same basemaps, BRO locations PMTiles, layers panel and
CPT triangles, without the address search and file loading.

- Geometry: `../data/model_extent.geojson` and `../data/site_plot.geojson`
  (WGS 84, written by `../data/make_project_geometry.py`), read by
  `src/project-geometry.ts`
- CPTs in the model extent: the PMTiles CPTs, picked with a `within` filter

```sh
npm install
npm run dev     # http://localhost:5173/iaeg2026-soft-soil-egm/
npm run build   # static site in dist/
```

`.github/workflows/pages.yml` builds and deploys on every push to `main` that
touches `site/`.
