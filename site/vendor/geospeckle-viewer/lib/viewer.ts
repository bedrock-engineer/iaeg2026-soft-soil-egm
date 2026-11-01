import type { AnyModel } from "@anywidget/types";
import {
  CameraController,
  DefaultViewerParams,
  SelectionExtension,
  Viewer,
  ViewerEvent,
} from "@speckle/viewer";
import type * as THREE from "three";
import { gunzipJson } from "./gunzip";
import { disposeMarker, markerObject } from "./markers";
import { MemoryLoader } from "./memory-loader";
import { bboxList, drawnElements, type TreeNodeLike } from "./scene";
import { elementOf, selectionData, singlePlacements } from "./selection";
import type { NodeLike } from "./selection";
import type { SpeckleObject, SpeckleViewerModel } from "./types";

/** A SpeckleViewer in its element, for a widget that adds to it */
export interface MountedViewer {
  viewer: Viewer;
  /** The viewer's element: position relative, so overlays can sit on it */
  container: HTMLDivElement;
  /** Shows a problem in red at the top left; "" clears it */
  showMessage(text: string): void;
  /** The widget's cleanup: stops loading, observing and the viewer */
  dispose(): void;
}

/**
 * Speckle's web viewer fed with v3 objects instead of a server URL, in the widget's element.
 * Each model in objects_gz (its root first) loads through a MemoryLoader into its own subtree.
 * After a load the widget reports object_count and scene_bbox; a click selects an element
 * (shift-click adds to the selection, a click on nothing clears it) and reports it in
 * selected. The model can hold more traits than SpeckleViewer's, for a widget that builds on
 * it (GeoSpeckleViewer).
 */
export async function mountSpeckleViewer<T extends SpeckleViewerModel>(
  model: AnyModel<T>,
  el: HTMLElement,
): Promise<MountedViewer> {
  // The traits this function reads and writes, whatever else the model holds
  const traits = model as unknown as AnyModel<SpeckleViewerModel>;
  const container = document.createElement("div");
  function size() {
    // A fixed height, or one that follows the notebook's width. The viewer's orbit controls set
    // no touch-action, so without one a touch screen scrolls the page on a drag and cancels the
    // camera's move a few pixels in, and pinches zoom the page.
    const height = traits.get("height");
    container.style.cssText = height
      ? `position: relative; width: 100%; height: ${height}px; touch-action: none;`
      : `position: relative; width: 100%; aspect-ratio: ${traits.get("aspect_ratio")}; touch-action: none;`;
  }
  size();
  el.appendChild(container);
  const message = document.createElement("div");
  message.style.cssText =
    "position: absolute; left: 8px; top: 6px; font: 12px sans-serif; color: #b00; pointer-events: none;";
  container.appendChild(message);

  const viewer = new Viewer(container, { ...DefaultViewerParams, verbose: false });
  await viewer.init();
  const camera = viewer.createExtension(CameraController);
  const selection = viewer.createExtension(SelectionExtension);

  let placedBy = new Map<string, SpeckleObject>();
  viewer.on(ViewerEvent.ObjectClicked, () => {
    // Read the extension's selection once it has handled the click (shift adds to it)
    setTimeout(() => {
      // tree-model's typings leave out a node's model and parent
      const nodes = selection.getSelectedNodes() as unknown as NodeLike[];
      const elements = nodes.map((node) => elementOf(node, placedBy));
      traits.set("selected", selectionData(elements));
      traits.save_changes();
    });
  });

  function report(objectCount: number, bbox: number[]) {
    traits.set("object_count", objectCount);
    traits.set("scene_bbox", bbox);
    traits.save_changes();
  }

  // Loads run one after the other; a load that a newer one has superseded stops early
  let loads = Promise.resolve();
  let latest = 0;
  async function load(generation: number) {
    if (generation !== latest) {
      return;
    }
    message.textContent = "";
    // Other objects: the old selection no longer applies
    if (traits.get("selected").length) {
      traits.set("selected", []);
      traits.save_changes();
    }
    await viewer.unloadAll();
    placedBy = new Map();
    const buffer = traits.get("objects_gz");
    if (!buffer || buffer.byteLength === 0) {
      report(0, []);
      return;
    }
    // One or more models, each its v3 objects with the root first
    const models = (await gunzipJson(buffer)) as SpeckleObject[][];
    for (const objects of models) {
      if (generation !== latest) {
        return;
      }
      for (const [member, instance] of singlePlacements(objects)) {
        placedBy.set(member, instance);
      }
      await viewer.loadObject(new MemoryLoader(viewer.getWorldTree(), objects), false);
    }
    camera.setCameraView(undefined, false);
    const renderer = viewer.getRenderer();
    const elements = drawnElements(
      // tree-model's typings leave out a node's model and parent
      viewer.getWorldTree().root.all(() => true) as unknown as TreeNodeLike[],
      new Set(renderer.batcher.getBatches().flatMap((batch) => batch.renderViews)),
      placedBy,
    );
    report(elements.size, bboxList(renderer.sceneBox));
  }
  function reload() {
    const generation = ++latest;
    loads = loads
      .then(() => load(generation))
      .catch((error: unknown) => {
        console.error("SpeckleViewer: loading the objects failed", error);
        message.textContent = `Loading failed: ${error}`;
      });
    return loads;
  }
  traits.on("change:objects_gz", reload);
  await reload();

  let markers: THREE.Group[] = [];
  function placeMarkers() {
    const scene = viewer.getRenderer().scene;
    for (const marker of markers) {
      scene.remove(marker);
      disposeMarker(marker);
    }
    markers = traits.get("markers").map(markerObject);
    for (const marker of markers) {
      scene.add(marker);
    }
    viewer.requestRender();
  }
  traits.on("change:markers", placeMarkers);
  placeMarkers();

  traits.on("change:height", size);
  traits.on("change:aspect_ratio", size);
  // The viewer itself only follows the window's size, not its container's
  const resizing = new ResizeObserver(() => viewer.resize());
  resizing.observe(container);
  return {
    viewer,
    container,
    showMessage(text: string) {
      message.textContent = text;
    },
    dispose() {
      latest++;
      resizing.disconnect();
      viewer.dispose();
    },
  };
}
