import proj4 from "proj4";
import polygonClipping from "polygon-clipping";
import { asyncBufferFromUrl, parquetMetadataAsync, parquetReadObjects } from "hyparquet";
import { compressors } from "hyparquet-compressors";

export const modelParquetUrl = "https://r2.eu.bedrock.engineer/bimpolars/rvt-advanced-sample/rvt-advanced-sample-combined-arch-str-bdf.parquet";

// Demo extent and grid settings only; geometry is constructed in the browser.
export const modelExtent = { centre_x: 122091, centre_y: 488736, xmin: 121900, xmax: 122400, ymin: 488500, ymax: 489000, zmin_nap: -50 };
proj4.defs("EPSG:28992", "+proj=sterea +lat_0=52.15616055555555 +lon_0=5.38763888888889 +k=0.9999079 +x_0=155000 +y_0=463000 +ellps=bessel +towgs84=565.4171,50.3319,465.5524,-0.398957,0.343988,-1.8774,4.0725 +units=m +no_defs");
const toWgs84 = (point: number[]) => proj4("EPSG:28992", "EPSG:4326", point.slice(0, 2));
const toRd = (point: number[]) => proj4("EPSG:4326", "EPSG:28992", point.slice(0, 2));
const rectangle = (x0: number, y0: number, x1: number, y1: number): GeoJSON.Polygon => ({ type: "Polygon", coordinates: [[[x0,y0], [x1,y0], [x1,y1], [x0,y1], [x0,y0]].map(toWgs84)] });
export const modelExtentFeature: GeoJSON.Feature<GeoJSON.Polygon, typeof modelExtent> = {
  type: "Feature", properties: modelExtent,
  geometry: rectangle(modelExtent.xmin, modelExtent.ymin, modelExtent.xmax, modelExtent.ymax),
};
export const geotopCells: GeoJSON.FeatureCollection<GeoJSON.Polygon, {geotop_x: number; geotop_y: number}> = { type: "FeatureCollection", features: [] };
for (let y = modelExtent.ymin; y < modelExtent.ymax; y += 100) {
  for (let x = modelExtent.xmin; x < modelExtent.xmax; x += 100) {
    geotopCells.features.push({ type: "Feature", properties: {geotop_x:x, geotop_y:y}, geometry: rectangle(x,y,x+100,y+100) });
  }
}
export function modelExtentBounds(): [[number,number],[number,number]] {
  const points = modelExtentFeature.geometry.coordinates.flat();
  return [[Math.min(...points.map(p=>p[0]!)), Math.min(...points.map(p=>p[1]!))], [Math.max(...points.map(p=>p[0]!)), Math.max(...points.map(p=>p[1]!))]];
}

function ringArea(ring: number[][]): number {
  return Math.abs(ring.reduce((sum, p, i) => {const next=ring[(i+1)%ring.length]!; return sum+p[0]!*next[1]!-next[0]!*p[1]!;},0))/2;
}

/** The actual geog WKB is decoded as GeoJSON by hyparquet's GeoParquet support.
 * Union in RD metres, ignoring Z for the horizontal footprint; retain its largest polygon.
 */
export function buildingFootprint(geometries: Array<GeoJSON.Polygon | GeoJSON.MultiPolygon>): GeoJSON.Feature<GeoJSON.Polygon> {
  const unique = new Map<string, polygonClipping.Polygon>();
  for (const geometry of geometries) {
    for (const polygon of geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates) {
      // Snap sub-millimetre projection noise before unioning thousands of
      // coincident floor/roof faces; retain a documented 1 mm horizontal precision.
      const projected = polygon.map(ring => {
        const points = ring.map(toRd).map(p => p.map(v => Math.round(v * 1000) / 1000));
        return points.filter((p, i) => i === 0 || p[0] !== points[i - 1]![0] || p[1] !== points[i - 1]![1]);
      }).filter(ring => ring.length >= 4 && ringArea(ring) > 0.000001) as polygonClipping.Polygon;
      if (projected[0] && projected[0].length >= 4) unique.set(JSON.stringify(projected), projected);
    }
  }
  if (!unique.size) throw new Error("The R2 Parquet contains no polygon footprints in its geog column.");
  let groups: polygonClipping.MultiPolygon[] = [...unique.values()].map(p => [p]);
  while (groups.length > 1) {
    const next: polygonClipping.MultiPolygon[] = [];
    for (let i=0; i<groups.length; i+=64) {
      const batch=groups.slice(i,i+64);
      next.push(polygonClipping.union(batch[0]!, ...batch.slice(1)));
    }
    groups=next;
  }
  const polygons=groups[0]!;
  const area = (p: polygonClipping.Polygon) => ringArea(p[0]!) - p.slice(1).reduce((sum,ring)=>sum+ringArea(ring),0);
  const largest=polygons.reduce((best,p)=>area(p)>area(best)?p:best);
  return { type: "Feature", properties: { name: "BIM footprint", source: modelParquetUrl, area_m2: area(largest) }, geometry: {type:"Polygon", coordinates:largest.map(ring=>ring.map(toWgs84))} };
}

let pendingFootprint: Promise<GeoJSON.Feature<GeoJSON.Polygon>> | undefined;
export function loadBuildingFootprint(): Promise<GeoJSON.Feature<GeoJSON.Polygon>> {
  // Reuse work across React StrictMode mounts; failures may be retried.
  pendingFootprint ??= (async () => {
    const file=await asyncBufferFromUrl({url:modelParquetUrl});
    const metadata=await parquetMetadataAsync(file);
    const geoValue=metadata.key_value_metadata?.find(entry=>entry.key==="geo")?.value;
    const geo=geoValue ? JSON.parse(geoValue) : undefined;
    if (geo?.columns?.geog?.encoding !== "WKB") throw new Error("Expected the R2 model's GeoParquet geog WKB column.");
    const rows=await parquetReadObjects({file, metadata, columns:["geog"], compressors, utf8:false});
    const geometries=rows.map(row=>row.geog).filter((g): g is GeoJSON.Polygon|GeoJSON.MultiPolygon => g?.type==="Polygon" || g?.type==="MultiPolygon");
    return buildingFootprint(geometries);
  })().catch(error=>{pendingFootprint=undefined;throw error;});
  return pendingFootprint;
}
