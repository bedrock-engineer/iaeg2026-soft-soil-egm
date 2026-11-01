import * as THREE from "three";
import type { Rings } from "./types";

/** The glTF attribute of EXT_mesh_features' first feature id set, as GLTFLoader names it */
const FEATURE_ID = "_feature_id_0";

/** Even-odd point in polygon over all rings, so that a point in a hole is outside */
export function insidePolygon(x: number, y: number, rings: Rings): boolean {
  let inside = false;
  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i];
      const [xj, yj] = ring[j];
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
        inside = !inside;
      }
    }
  }
  return inside;
}

/** A polygon with its plan bounds, to skip the vertices far from it */
interface Area {
  rings: Rings;
  min: [number, number];
  max: [number, number];
}

function area(rings: Rings): Area {
  const points = rings.flat();
  return {
    rings,
    min: [Math.min(...points.map(([x]) => x)), Math.min(...points.map(([, y]) => y))],
    max: [Math.max(...points.map(([x]) => x)), Math.max(...points.map(([, y]) => y))],
  };
}

function inside(x: number, y: number, areas: Area[]): boolean {
  return areas.some(
    ({ rings, min, max }) =>
      x >= min[0] && x <= max[0] && y >= min[1] && y <= max[1] && insidePolygon(x, y, rings),
  );
}

/**
 * The factor that takes an attribute's stored values to its values: three.js 0.140 returns
 * quantized (normalized integer) attributes as stored.
 */
export function denormalizeScale(attribute: THREE.BufferAttribute): number {
  if (!attribute.normalized) {
    return 1;
  }
  const array = attribute.array;
  if (array instanceof Int8Array) {
    return 1 / 127;
  }
  if (array instanceof Uint8Array) {
    return 1 / 255;
  }
  if (array instanceof Int16Array) {
    return 1 / 32767;
  }
  if (array instanceof Uint16Array) {
    return 1 / 65535;
  }
  return 1;
}

/** The features hideFeaturesWithin dropped, and the heights their vertices span */
export interface HiddenFeatures {
  ids: Set<number>;
  /** [zmin, zmax] of the dropped features' vertices in the world, [] for none */
  heights: number[];
}

/**
 * Drops the triangles of every feature (an EXT_mesh_features id) with more than half of its
 * vertices inside one of the polygons, which are in the world: matrix takes the mesh there.
 *
 * @returns the ids of the features dropped, and the heights they span in the world
 */
export function hideFeaturesWithin(
  geometry: THREE.BufferGeometry,
  matrix: THREE.Matrix4,
  polygons: Rings[],
): HiddenFeatures {
  const hidden: HiddenFeatures = { ids: new Set(), heights: [] };
  const featureIds = geometry.getAttribute(FEATURE_ID) as THREE.BufferAttribute | undefined;
  if (!featureIds || !geometry.index || polygons.length === 0) {
    return hidden;
  }
  const areas = polygons.map(area);
  const position = geometry.getAttribute("position") as THREE.BufferAttribute;
  const scale = denormalizeScale(position);
  const vertex = new THREE.Vector3();
  // Feature id: [vertices inside, vertices, zmin, zmax]
  const counts = new Map<number, [number, number, number, number]>();
  for (let i = 0; i < position.count; i++) {
    const id = featureIds.getX(i);
    let count = counts.get(id);
    if (!count) {
      count = [0, 0, Infinity, -Infinity];
      counts.set(id, count);
    }
    vertex.fromBufferAttribute(position, i).multiplyScalar(scale).applyMatrix4(matrix);
    if (inside(vertex.x, vertex.y, areas)) {
      count[0]++;
    }
    count[1]++;
    count[2] = Math.min(count[2], vertex.z);
    count[3] = Math.max(count[3], vertex.z);
  }
  for (const [id, [within, total, zmin, zmax]] of counts) {
    if (within > total / 2) {
      hidden.ids.add(id);
      hidden.heights = spanHeights(hidden.heights, [zmin, zmax]);
    }
  }
  if (hidden.ids.size > 0) {
    // GLTFLoader's indices: one of these, by the vertex count
    const index = geometry.index.array as Uint8Array | Uint16Array | Uint32Array;
    const kept = index.filter(
      (_: number, i: number) => !hidden.ids.has(featureIds.getX(index[i - (i % 3)])),
    );
    geometry.setIndex(new THREE.BufferAttribute(kept, 1));
  }
  return hidden;
}

/** The [zmin, zmax] that spans both, where [] spans nothing */
export function spanHeights(a: number[], b: number[]): number[] {
  if (a.length === 0) {
    return b;
  }
  if (b.length === 0) {
    return a;
  }
  return [Math.min(a[0], b[0]), Math.max(a[1], b[1])];
}
