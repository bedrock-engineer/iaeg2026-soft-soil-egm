import proj4 from "proj4";
import cptRecords from "./data/cpts.json";

// RD New with the 7-parameter +towgs84 shift (~0.5 m accuracy), the
// same definition bro-xml-app registers before its datum grid loads.
// Plenty for drawing a 400 × 500 m box on a web map.
proj4.defs(
  "EPSG:28992",
  "+proj=sterea +lat_0=52.1561605555556 +lon_0=5.38763888888889 +k=0.9999079 +x_0=155000 +y_0=463000 +ellps=bessel +towgs84=565.417,50.3319,465.552,-0.398957,0.343988,-1.8774,4.0725 +units=m +no_defs +type=crs",
);

type RdPoint = [x: number, y: number];

function rdToLngLat([x, y]: RdPoint): [number, number] {
  return proj4("EPSG:28992", "EPSG:4326", [x, y]) as [number, number];
}

/**
 * Centre of the model, the plot centre from the bedrock-experiments
 * nl_amsterdam demo (RD New, EPSG:28992).
 */
export const modelCentre: RdPoint = [122_091, 488_736];

/**
 * Model extent the GeoTOP voxels are taken from: the centre ±200 m,
 * plus one extra 100 m GeoTOP row to the north. 400 m east–west by
 * 500 m north–south, bottom at −50 m NAP.
 */
export const modelExtent = {
  xmin: modelCentre[0] - 200,
  xmax: modelCentre[0] + 200,
  ymin: modelCentre[1] - 200,
  ymax: modelCentre[1] + 300,
  zmin: -50,
};

/**
 * The fictitious building plot from bedrock-experiments
 * nl_amsterdam/data/04_feature/site_plot_rdnap_epsg7415.geojson.
 */
const sitePlotRd: Array<RdPoint> = [
  [122027.64070962, 488729.81892801],
  [122030.00644953, 488738.10909897],
  [122028.59624385, 488750.3614188],
  [122035.77172481, 488758.13930359],
  [122096.39231516, 488775.978851],
  [122109.80814416, 488781.26662536],
  [122123.10771052, 488790.78016499],
  [122136.66018253, 488794.91482472],
  [122139.94448297, 488796.62133805],
  [122157.55032302, 488802.31340892],
  [122158.11253251, 488800.00514861],
  [122170.07445062, 488803.81440499],
  [122171.75258187, 488802.84302274],
  [122191.19470579, 488775.26345761],
  [122074.11883562, 488689.34674238],
  [122072.64073557, 488691.44512356],
  [122068.86331167, 488691.59036584],
  [122067.90519318, 488692.26892729],
  [122067.11905607, 488693.47447109],
  [122054.44721844, 488684.31678759],
  [122052.34070592, 488686.01127232],
  [122045.16524171, 488696.26171883],
  [122043.06596513, 488695.43553506],
  [122041.65879244, 488697.34140216],
  [122040.71640474, 488696.77155612],
  [122036.57302339, 488703.37685234],
  [122027.64070962, 488729.81892801],
];

export function modelExtentGeoJSON(): GeoJSON.Feature<GeoJSON.Polygon> {
  const { xmin, xmax, ymin, ymax } = modelExtent;
  const ring: Array<RdPoint> = [
    [xmin, ymin],
    [xmax, ymin],
    [xmax, ymax],
    [xmin, ymax],
    [xmin, ymin],
  ];
  return {
    type: "Feature",
    geometry: { type: "Polygon", coordinates: [ring.map(rdToLngLat)] },
    properties: { name: "GeoTOP model extent" },
  };
}

export function sitePlotGeoJSON(): GeoJSON.Feature<GeoJSON.Polygon> {
  return {
    type: "Feature",
    geometry: { type: "Polygon", coordinates: [sitePlotRd.map(rdToLngLat)] },
    properties: { name: "Site plot" },
  };
}

/**
 * The 66 BRO CPTs inside the model extent, from
 * research/bro-cpt-coverage_cpts.csv (ticket #2).
 */
export function cptGeoJSON(): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: cptRecords.map((cpt) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: rdToLngLat([cpt.x, cpt.y]) },
      properties: { ...cpt },
    })),
  };
}

/** Model extent bounds as [[west, south], [east, north]]. */
export function modelExtentBounds(): [[number, number], [number, number]] {
  const { xmin, xmax, ymin, ymax } = modelExtent;
  const [west, south] = rdToLngLat([xmin, ymin]);
  const [east, north] = rdToLngLat([xmax, ymax]);
  return [
    [west, south],
    [east, north],
  ];
}
