import type { RenderProps } from "@anywidget/types";
import { ContextTiles, type TilesReport } from "./lib/context-tiles";
import { disposeGroundMap, GroundInView, groundMapImage, groundMapMesh } from "./lib/ground-map";
import { isGroundMap, mapCorners, OSM_ATTRIBUTION } from "./lib/map-tiles";
import { mountSpeckleViewer } from "./lib/viewer";
import type { GeoSpeckleViewerModel, GroundMap } from "./lib/types";
import type * as THREE from "three";

/** How long the surroundings report waits for more tiles before it goes to Python */
const REPORT_DELAY_MS = 250;

/** The ground map's plane in the world, [xmin, ymin, xmax, ymax] */
function planeBounds(groundMap: GroundMap): number[] {
  const corners = mapCorners(groundMap);
  const xs = corners.map(([x]) => x);
  const ys = corners.map(([, y]) => y);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

/**
 * SpeckleViewer with the model's surroundings: an OpenStreetMap ground map under it and 3D
 * Tiles around it, such as PDOK's 3D BAG, without the buildings the model takes the place of.
 * The front end reports what it shows in surroundings.
 */
export default {
  async render({ model, el }: RenderProps<GeoSpeckleViewerModel>) {
    const mounted = await mountSpeckleViewer(model, el);
    const { viewer, container } = mounted;
    const groundInView = viewer.createExtension(GroundInView);
    const contextTiles = viewer.createExtension(ContextTiles);

    let groundBounds: number[] = [];
    let tilesReport: TilesReport = { tiles: 0, hiddenFeatures: 0, hiddenHeights: [] };
    let reporting: ReturnType<typeof setTimeout> | undefined;
    function report() {
      clearTimeout(reporting);
      reporting = setTimeout(() => {
        model.set("surroundings", {
          ground_map: groundBounds,
          tiles: tilesReport.tiles,
          hidden_features: tilesReport.hiddenFeatures,
          hidden_heights: tilesReport.hiddenHeights,
        });
        model.save_changes();
      }, REPORT_DELAY_MS);
    }
    contextTiles.onChange = (tiles) => {
      tilesReport = tiles;
      report();
    };

    const attribution = document.createElement("div");
    attribution.style.cssText =
      "position: absolute; right: 4px; bottom: 2px; font: 11px sans-serif; color: #555; pointer-events: none;";
    container.appendChild(attribution);
    function updateAttribution() {
      const credits = [
        ...(isGroundMap(model.get("ground_map")) ? [OSM_ATTRIBUTION] : []),
        ...model
          .get("tilesets")
          .map((entry) => entry.attribution)
          .filter(Boolean),
      ];
      attribution.textContent = credits.join(" | ");
    }

    // Ground maps load one after the other; one that a newer one has superseded is dropped
    let ground: THREE.Mesh | null = null;
    let latest = 0;
    async function placeGroundMap() {
      const generation = ++latest;
      updateAttribution();
      const groundMap = model.get("ground_map");
      let mesh: THREE.Mesh | null = null;
      if (isGroundMap(groundMap)) {
        try {
          mesh = groundMapMesh(groundMap, await groundMapImage(groundMap));
        } catch (error) {
          console.error("GeoSpeckleViewer: the ground map failed", error);
          mounted.showMessage(`The ground map failed: ${error}`);
        }
      }
      if (generation !== latest) {
        if (mesh) {
          disposeGroundMap(mesh);
        }
        return;
      }
      const scene = viewer.getRenderer().scene;
      if (ground) {
        scene.remove(ground);
        disposeGroundMap(ground);
      }
      ground = groundInView.ground = mesh;
      if (mesh) {
        scene.add(mesh);
      }
      groundBounds = mesh && isGroundMap(groundMap) ? planeBounds(groundMap) : [];
      report();
      viewer.requestRender();
    }
    function placeTilesets() {
      contextTiles.setTilesets(model.get("tilesets"));
      updateAttribution();
    }
    model.on("change:tilesets", placeTilesets);
    placeTilesets();

    // The map's tiles arrive while the model is already in view
    model.on("change:ground_map", placeGroundMap);
    void placeGroundMap();

    return () => {
      latest++;
      clearTimeout(reporting);
      contextTiles.clear();
      mounted.dispose();
    };
  },
};
