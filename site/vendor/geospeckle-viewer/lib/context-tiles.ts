import { Extension, ObjectLayers } from "@speckle/viewer";
import { TilesRenderer } from "3d-tiles-renderer";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { hideFeaturesWithin, spanHeights } from "./hide-features";
import type { Tileset } from "./types";

/** What the tiles of every tileset show, for the surroundings trait */
export interface TilesReport {
  tiles: number;
  hiddenFeatures: number;
  /** [zmin, zmax] of the hidden features in the world, [] for none */
  hiddenHeights: number[];
}

/**
 * 3D Tiles in the viewer's world. Each tileset entry holds a tileset (its JSON, with absolute
 * content URLs) and ecef_to_world, a column-major 4x4 from ECEF (where the tiles are) to the
 * world. Features mostly inside one of the entry's hide_within polygons are left out, to make
 * room for the model itself. The tiles follow the viewer's camera every frame, request a
 * render when one arrives, and sit on the PROPS layer, so object_count and scene_bbox leave
 * them out. onChange hears when the loaded tiles change.
 */
export class ContextTiles extends Extension {
  private tilesets: { tiles: TilesRenderer; url: string }[] = [];
  /** The features hidden in each loaded tile content, and the heights they span */
  private loaded = new Map<object, { hidden: number; heights: number[] }>();
  onChange: (report: TilesReport) => void = () => {};

  report(): TilesReport {
    let hiddenFeatures = 0;
    let hiddenHeights: number[] = [];
    for (const { hidden, heights } of this.loaded.values()) {
      hiddenFeatures += hidden;
      hiddenHeights = spanHeights(hiddenHeights, heights);
    }
    return { tiles: this.loaded.size, hiddenFeatures, hiddenHeights };
  }

  setTilesets(tilesets: Tileset[]): void {
    this.clear();
    const scene = this.viewer.getRenderer().scene;
    this.tilesets = tilesets.map(({ tileset, ecef_to_world, hide_within = [] }) => {
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(tileset)], { type: "application/json" }),
      );
      const tiles = new TilesRenderer(url);
      // PDOK's tiles need EXT_meshopt_compression
      const gltfLoader = new GLTFLoader(tiles.manager);
      gltfLoader.setMeshoptDecoder(MeshoptDecoder);
      tiles.manager.addHandler(/\.(gltf|glb)$/g, gltfLoader);
      tiles.group.matrixAutoUpdate = false;
      tiles.group.matrix.fromArray(ecef_to_world);
      tiles.addEventListener("load-model", ({ scene: content, tile }) => {
        const hidden = new Set<number>();
        let heights: number[] = [];
        content.traverse((object) => {
          object.layers.set(ObjectLayers.PROPS);
          const mesh = object as THREE.Mesh;
          if (mesh.isMesh && hide_within.length) {
            // The tile's content is not under tiles.group yet
            object.updateWorldMatrix(true, false);
            const toWorld = tiles.group.matrix.clone().multiply(object.matrixWorld);
            const dropped = hideFeaturesWithin(mesh.geometry, toWorld, hide_within);
            for (const id of dropped.ids) {
              hidden.add(id);
            }
            heights = spanHeights(heights, dropped.heights);
          }
        });
        this.loaded.set(tile, { hidden: hidden.size, heights });
        this.onChange(this.report());
        this.viewer.requestRender();
      });
      tiles.addEventListener("dispose-model", ({ tile }) => {
        this.loaded.delete(tile);
        this.onChange(this.report());
      });
      scene.add(tiles.group);
      return { tiles, url };
    });
    this.onChange(this.report());
    this.viewer.requestRender();
  }

  clear(): void {
    const scene = this.viewer.getRenderer().scene;
    for (const { tiles, url } of this.tilesets) {
      scene.remove(tiles.group);
      tiles.dispose();
      URL.revokeObjectURL(url);
    }
    this.tilesets = [];
    this.loaded.clear();
  }

  override onEarlyUpdate(): void {
    const renderer = this.viewer.getRenderer();
    const camera = renderer.renderingCamera;
    if (!camera) {
      return;
    }
    for (const { tiles } of this.tilesets) {
      tiles.setCamera(camera);
      tiles.setResolutionFromRenderer(camera, renderer.renderer);
      camera.updateMatrixWorld();
      tiles.group.updateMatrixWorld(true);
      tiles.update();
    }
  }
}
