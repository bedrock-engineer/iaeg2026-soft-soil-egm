/** One Speckle v3 object as parsed JSON */
export interface SpeckleObject {
  id: string;
  speckle_type?: string;
  applicationId?: string;
  [field: string]: unknown;
}

/** Axes and a label at a named point: the TS mirror of the Python `Marker` */
export interface Marker {
  name: string;
  /** [x, y, z] in the viewer's world: metres */
  position: [number, number, number];
  /** Length of the axes in metres */
  size?: number;
}

/** The synced traits: the TS mirror of SpeckleViewer's traitlets, change them together */
export interface SpeckleViewerModel {
  /** Gzipped JSON of one or more models, each an array of v3 objects, root first */
  objects_gz: DataView<ArrayBuffer> | ArrayBuffer;
  /** Height in pixels; null: the height follows the width by aspect_ratio */
  height: number | null;
  /** Width over height, when height is null */
  aspect_ratio: number;
  /** Raw data of the selected elements, without their geometry and children */
  selected: Record<string, unknown>[];
  markers: Marker[];
  /** Set by the front end: the number of elements the viewer draws, as a click selects them */
  object_count: number;
  /** Set by the front end: [xmin, ymin, zmin, xmax, ymax, zmax] in metres, [] when empty */
  scene_bbox: number[];
}

/**
 * A raster map under the model, north up, over bounds: the TS mirror of the Python
 * `GroundMap`. The image is width x height pixels of Web Mercator tiles; its corners go to the
 * viewer's world through lnglat_to_world.
 */
export interface GroundMap {
  /** [west, south, east, north] in degrees */
  bounds: [number, number, number, number];
  /** The image's size in pixels; the height follows the bounds' shape in Web Mercator */
  width: number;
  height: number;
  /** An affine [a, b, c, d, e, f] from lon/lat to the world: x = a lon + b lat + c, y = d lon + e lat + f */
  lnglat_to_world: [number, number, number, number, number, number];
  /** The map's height in the world, metres */
  z: number;
  opacity: number;
}

/** A polygon as rings of [x, y] in the viewer's world (metres): the exterior, then the holes */
export type Rings = [number, number][][];

/** 3D Tiles around the model: the TS mirror of the Python `Tileset` */
export interface Tileset {
  /** The tileset JSON, with absolute content URLs */
  tileset: Record<string, unknown>;
  /** Column-major 4x4 from ECEF, where the tiles are, to the viewer's world */
  ecef_to_world: number[];
  /** The credit line the viewer shows for the tiles */
  attribution?: string;
  /** Features (EXT_mesh_features ids) mostly inside one of these polygons are left out */
  hide_within?: Rings[];
}

/** What the surroundings show, set by the front end; the TS mirror of the trait's comment */
export interface Surroundings {
  /** The ground map's plane in the world, [xmin, ymin, xmax, ymax], [] without one */
  ground_map: number[];
  /** Tile contents loaded */
  tiles: number;
  /** Features of the loaded tiles left out by hide_within */
  hidden_features: number;
  /** [zmin, zmax] of those features in the world, [] for none: where the tiles stand */
  hidden_heights: number[];
}

/** GeoSpeckleViewer's traits: SpeckleViewer's and its surroundings */
export interface GeoSpeckleViewerModel extends SpeckleViewerModel {
  /** {} for none */
  ground_map: GroundMap | Record<string, never>;
  tilesets: Tileset[];
  surroundings: Surroundings;
}
