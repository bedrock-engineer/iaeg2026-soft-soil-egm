// The project geometry lives in the repo's data/ folder, so the
// notebooks and this site read the same files. See
// data/make_project_geometry.py.
import modelExtentText from "../../data/model_extent.geojson?raw";
import sitePlotText from "../../data/site_plot.geojson?raw";

type PolygonCollection<P> = GeoJSON.FeatureCollection<GeoJSON.Polygon, P>;

function firstFeature<P>(text: string): GeoJSON.Feature<GeoJSON.Polygon, P> {
  const feature = (JSON.parse(text) as PolygonCollection<P>).features[0];
  if (!feature) {
    throw new Error("Expected a feature in the project geometry");
  }
  return feature;
}

/** RD New (EPSG:28992) definition of the model extent. */
interface ModelExtent {
  centre_x: number;
  centre_y: number;
  xmin: number;
  xmax: number;
  ymin: number;
  ymax: number;
  zmin_nap: number;
}

/**
 * Model extent the GeoTOP voxels are taken from: the plot centre
 * ±200 m, plus one extra 100 m GeoTOP row to the north.
 */
export const modelExtentFeature = firstFeature<ModelExtent>(modelExtentText);

export const modelExtent = modelExtentFeature.properties;

/** The fictitious building plot from bedrock-experiments nl_amsterdam (site.gpkg, layer "plot"). */
export const sitePlotFeature =
  firstFeature<GeoJSON.GeoJsonProperties>(sitePlotText);

/** Model extent bounds as [[west, south], [east, north]]. */
export function modelExtentBounds(): [[number, number], [number, number]] {
  const positions = modelExtentFeature.geometry.coordinates.flat();
  const lngs = positions.map(([lng = 0]) => lng);
  const lats = positions.map(([, lat = 0]) => lat);
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ];
}
