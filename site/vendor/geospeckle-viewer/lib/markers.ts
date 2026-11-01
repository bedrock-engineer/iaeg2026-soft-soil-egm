import { ObjectLayers } from "@speckle/viewer";
import * as THREE from "three";
import type { Marker } from "./types";

/**
 * Axes (x red, y green, z blue) and a label at a named point in the viewer's world, drawn on
 * top of the model. They sit on the PROPS layer, as the viewer's own helpers do, and go into
 * the scene directly rather than through the viewer's batches, so object_count and
 * scene_bbox leave them out.
 */
export function markerObject({ name, position, size = 5 }: Marker): THREE.Group {
  const group = new THREE.Group();
  group.position.fromArray(position);
  const axes = new THREE.AxesHelper(size);
  (axes.material as THREE.Material).depthTest = false;
  group.add(axes);

  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d")!;
  context.font = "28px sans-serif";
  canvas.width = Math.ceil(context.measureText(name).width) + 16;
  canvas.height = 40;
  // Resizing the canvas resets its context
  context.font = "28px sans-serif";
  context.fillStyle = "rgba(255, 255, 255, 0.85)";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#222";
  context.fillText(name, 8, 29);
  const label = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false }),
  );
  label.scale.set(canvas.width / canvas.height, 1, 1).multiplyScalar(size / 4);
  label.position.set(0, 0, size * 1.2);
  group.add(label);

  group.traverse((object) => {
    object.layers.set(ObjectLayers.PROPS);
    object.renderOrder = 10;
  });
  return group;
}

/** Frees a marker's GPU resources once it is out of the scene */
export function disposeMarker(group: THREE.Group): void {
  group.traverse((object) => {
    const { geometry, material } = object as THREE.Mesh;
    geometry?.dispose();
    for (const each of Array.isArray(material) ? material : material ? [material] : []) {
      (each as THREE.SpriteMaterial).map?.dispose();
      each.dispose();
    }
  });
}
