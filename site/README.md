# Project home page

The home page of this repo, published with GitHub Pages at
<https://bedrock-engineer.github.io/iaeg2026-soft-soil-egm/>.

It shows the GeoTOP model extent, the fictitious site plot and the BRO CPTs
inside the extent on a MapLibre map. The map is ported from
[bro-xml-app](https://github.com/bedrock-engineer/bro-xml-app)
(`app/components/map/`): same basemaps, BRO locations PMTiles, layers panel and
CPT triangles, without the address search and file loading.

- Geometry: `src/project-geometry.ts` (RD New coordinates, converted with proj4)
- CPTs: `src/data/cpts.json`, from `research/bro-cpt-coverage_cpts.csv`

```sh
npm install
npm run dev     # http://localhost:5173/iaeg2026-soft-soil-egm/
npm run build   # static site in dist/
```

`.github/workflows/pages.yml` builds and deploys on every push to `main` that
touches `site/`.
