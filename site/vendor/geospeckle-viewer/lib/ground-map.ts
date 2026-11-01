import { Extension, ObjectLayers } from "@speckle/viewer";
import * as THREE from "three";
import { mapCorners, OSM_TILES, tilesFor, tileUrl } from "./map-tiles";
import type { GroundMap } from "./types";

/**
 * The map's image: its OpenStreetMap tiles drawn on a canvas, north up, exactly over its
 * bounds. Tiles that fail to load stay blank; if all of them fail, so does this.
 */
export async function groundMapImage(
  groundMap: GroundMap,
  template = OSM_TILES,
): Promise<HTMLCanvasElement> {
  const canvas = document.createElement("canvas");
  canvas.width = groundMap.width;
  canvas.height = groundMap.height;
  const context = canvas.getContext("2d")!;
  const tiles = tilesFor(groundMap);
  const loaded = await Promise.allSettled(
    tiles.map(async (tile) => {
      const response = await fetch(tileUrl(template, tile));
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      // A bitmap from the bytes, so the canvas stays readable as a texture
      const bitmap = await createImageBitmap(await response.blob());
      context.drawImage(bitmap, tile.left, tile.top, tile.width, tile.height);
      bitmap.close();
    }),
  );
  const failed = loaded.filter((result) => result.status === "rejected");
  if (failed.length === tiles.length) {
    throw new Error(`none of the ${tiles.length} map tiles loaded: ${failed[0]?.reason}`);
  }
  return canvas;
}

/**
 * The map's image on a plane at its height in the world, on the PROPS layer as the viewer's
 * own helpers are, so that object_count and scene_bbox leave it out.
 */
export function groundMapMesh(groundMap: GroundMap, image: HTMLCanvasElement): THREE.Mesh {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(mapCorners(groundMap).flat(), 3),
  );
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 1], 2));
  geometry.setIndex([0, 1, 2, 0, 2, 3]);
  const texture = new THREE.CanvasTexture(image);
  texture.encoding = THREE.sRGBEncoding;
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    side: THREE.DoubleSide,
    transparent: groundMap.opacity < 1,
    opacity: groundMap.opacity,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.layers.set(ObjectLayers.PROPS);
  return mesh;
}

/** Frees a ground map's GPU resources once it is out of the scene */
export function disposeGroundMap(mesh: THREE.Mesh): void {
  const material = mesh.material as THREE.MeshBasicMaterial;
  material.map?.dispose();
  material.dispose();
  mesh.geometry.dispose();
}

/**
 * The camera controller fits the near and far planes to the models alone; this pushes the
 * far plane out to the ground map's farthest corner, so the map is drawn whole.
 */
export class GroundInView extends Extension {
  ground: THREE.Mesh | null = null;

  override onLateUpdate(): void {
    const camera = this.viewer.getRenderer().renderingCamera;
    if (!this.ground || !camera) {
      return;
    }
    const corners = this.ground.geometry.getAttribute("position");
    const corner = new THREE.Vector3();
    let farthest = 0;
    for (let i = 0; i < corners.count; i++) {
      corner.fromBufferAttribute(corners as THREE.BufferAttribute, i);
      farthest = Math.max(farthest, camera.position.distanceTo(corner));
    }
    if (camera.far < 1.05 * farthest) {
      camera.far = 1.05 * farthest;
      camera.updateProjectionMatrix();
    }
  }
}
