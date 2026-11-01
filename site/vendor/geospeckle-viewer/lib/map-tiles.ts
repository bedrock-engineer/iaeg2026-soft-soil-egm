import type { GroundMap } from "./types";

/** OpenStreetMap's standard raster tiles, Web Mercator, 256 pixels */
export const OSM_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const OSM_MAX_ZOOM = 19;
export const OSM_ATTRIBUTION = "© OpenStreetMap contributors";
const TILE_SIZE = 256;

/** Whether the ground_map trait holds a map: {} holds none */
export function isGroundMap(value: GroundMap | Record<string, never>): value is GroundMap {
  return "bounds" in value;
}

/** A longitude as a Web Mercator tile coordinate at a zoom level: 0 at 180 W */
export function tileX(lon: number, zoom: number): number {
  return ((lon + 180) / 360) * 2 ** zoom;
}

/** A latitude as a Web Mercator tile coordinate at a zoom level: 0 at the north edge */
export function tileY(lat: number, zoom: number): number {
  const phi = (lat * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2) * 2 ** zoom;
}

/** One tile of a map image: its z/x/y and where it goes in the image, in pixels */
export interface TilePlacement {
  z: number;
  x: number;
  y: number;
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * The tiles that cover a map's bounds, and where each goes in its width x height image. The
 * zoom level is the one whose tiles come closest to the image's resolution, as a web map
 * picks it, up to maxZoom.
 */
export function tilesFor(
  { bounds, width, height }: Pick<GroundMap, "bounds" | "width" | "height">,
  maxZoom = OSM_MAX_ZOOM,
): TilePlacement[] {
  const [west, south, east, north] = bounds;
  const across = tileX(east, 0) - tileX(west, 0);
  const z = Math.max(0, Math.min(maxZoom, Math.round(Math.log2(width / (TILE_SIZE * across)))));
  const [x0, x1] = [tileX(west, z), tileX(east, z)];
  const [y0, y1] = [tileY(north, z), tileY(south, z)];
  // Image pixels per tile
  const [scaleX, scaleY] = [width / (x1 - x0), height / (y1 - y0)];
  const tiles: TilePlacement[] = [];
  for (let y = Math.floor(y0); y < y1; y++) {
    for (let x = Math.floor(x0); x < x1; x++) {
      tiles.push({
        z,
        x,
        y,
        left: (x - x0) * scaleX,
        top: (y - y0) * scaleY,
        width: scaleX,
        height: scaleY,
      });
    }
  }
  return tiles;
}

/** A tile's URL from a {z}/{x}/{y} template */
export function tileUrl(template: string, { z, x, y }: TilePlacement): string {
  return template.replace("{z}", `${z}`).replace("{x}", `${x}`).replace("{y}", `${y}`);
}

/** The world's [x, y, z] of a lon/lat on the ground map */
export function mapToWorld(
  { lnglat_to_world: t, z }: Pick<GroundMap, "lnglat_to_world" | "z">,
  lon: number,
  lat: number,
): [number, number, number] {
  return [t[0] * lon + t[1] * lat + t[2], t[3] * lon + t[4] * lat + t[5], z];
}

/** The ground map's corners in the world: south-west, south-east, north-east, north-west */
export function mapCorners(groundMap: GroundMap): [number, number, number][] {
  const [west, south, east, north] = groundMap.bounds;
  return [
    mapToWorld(groundMap, west, south),
    mapToWorld(groundMap, east, south),
    mapToWorld(groundMap, east, north),
    mapToWorld(groundMap, west, north),
  ];
}
