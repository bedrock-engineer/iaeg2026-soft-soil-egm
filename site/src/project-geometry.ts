import proj4 from "proj4";
import polygonClipping from "polygon-clipping";

export const modelParquetUrl =
  "https://r2.eu.bedrock.engineer/nl-amsterdam-noord/rvt_advanced_sample_combined_arch_str.parquet";

proj4.defs(
  "EPSG:28992",
  "+proj=sterea +lat_0=52.15616055555555 +lon_0=5.38763888888889 +k=0.9999079 +x_0=155000 +y_0=463000 +ellps=bessel +towgs84=565.4171,50.3319,465.5524,-0.398957,0.343988,-1.8774,4.0725 +units=m +no_defs",
);
const toWgs84 = (point: number[]) =>
  proj4("EPSG:28992", "EPSG:4326", point.slice(0, 2));
const toRd = (point: number[]) =>
  proj4("EPSG:4326", "EPSG:28992", point.slice(0, 2));
function ringArea(ring: number[][]): number {
  return (
    Math.abs(
      ring.reduce((sum, p, i) => {
        const next = ring[(i + 1) % ring.length]!;
        return sum + p[0]! * next[1]! - next[0]! * p[1]!;
      }, 0),
    ) / 2
  );
}

/** The actual geog WKB is decoded as GeoJSON by hyparquet's GeoParquet support.
 * Union in RD meters, ignoring Z for the horizontal footprint; retain its largest polygon.
 * Returns it in longitude and latitude, and its exterior ring in RD New for the cross sections.
 */
export function buildingFootprint(
  geometries: Array<GeoJSON.Polygon | GeoJSON.MultiPolygon>,
): { outline: GeoJSON.Feature<GeoJSON.Polygon>; ring: number[][] } {
  const unique = new Map<string, polygonClipping.Polygon>();
  for (const geometry of geometries) {
    for (const polygon of geometry.type === "Polygon"
      ? [geometry.coordinates]
      : geometry.coordinates) {
      // Snap sub-millimeter projection noise before unioning thousands of
      // coincident floor/roof faces; retain a documented 1 mm horizontal precision.
      const projected = polygon
        .map((ring) => {
          const points = ring
            .map(toRd)
            .map((p) => p.map((v) => Math.round(v * 1000) / 1000));
          return points.filter(
            (p, i) =>
              i === 0 ||
              p[0] !== points[i - 1]![0] ||
              p[1] !== points[i - 1]![1],
          );
        })
        .filter(
          (ring) => ring.length >= 4 && ringArea(ring) > 0.000001,
        ) as polygonClipping.Polygon;
      if (projected[0] && projected[0].length >= 4)
        unique.set(JSON.stringify(projected), projected);
    }
  }
  if (!unique.size)
    throw new Error(
      "The R2 Parquet contains no polygon footprints in its geog column.",
    );
  let groups: polygonClipping.MultiPolygon[] = [...unique.values()].map((p) => [
    p,
  ]);
  while (groups.length > 1) {
    const next: polygonClipping.MultiPolygon[] = [];
    for (let i = 0; i < groups.length; i += 64) {
      const batch = groups.slice(i, i + 64);
      next.push(polygonClipping.union(batch[0]!, ...batch.slice(1)));
    }
    groups = next;
  }
  const polygons = groups[0]!;
  const area = (p: polygonClipping.Polygon) =>
    ringArea(p[0]!) - p.slice(1).reduce((sum, ring) => sum + ringArea(ring), 0);
  const largest = polygons.reduce((best, p) =>
    area(p) > area(best) ? p : best,
  );
  return {
    outline: {
      type: "Feature",
      properties: {
        name: "BIM footprint",
        source: modelParquetUrl,
        area_m2: area(largest),
      },
      geometry: {
        type: "Polygon",
        coordinates: largest.map((ring) => ring.map(toWgs84)),
      },
    },
    ring: largest[0]!,
  };
}
