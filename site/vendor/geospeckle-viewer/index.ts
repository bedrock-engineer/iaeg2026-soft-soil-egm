import type { RenderProps } from "@anywidget/types";
import geospeckleViewer from "./geospeckle-viewer";
import type { GeoSpeckleViewerModel } from "./lib/types";
import { StaticModel } from "./static-model";

export { StaticModel } from "./static-model";
export type {
  GeoSpeckleViewerModel,
  GroundMap,
  Marker,
  Rings,
  SpeckleObject,
  SpeckleViewerModel,
  Surroundings,
  Tileset,
} from "./lib/types";

/** What mountGeoSpeckleViewer takes: the model's objects, and any other trait to set */
export type GeoSpeckleViewerTraits = Pick<GeoSpeckleViewerModel, "objects_gz"> &
  Partial<GeoSpeckleViewerModel>;

/** A GeoSpeckleViewer on a web page */
export interface MountedGeoSpeckleViewer {
  /**
   * The traits: set one to change the viewer, and follow `change:<trait>` for what it reports
   * (`selected`, `object_count`, `scene_bbox`, `surroundings`). Add handlers before awaiting
   * `loaded`, since the first report comes before it resolves.
   */
  model: StaticModel<GeoSpeckleViewerModel>;
  /** Resolves once the objects are in view */
  loaded: Promise<void>;
  /** Stops loading and frees the viewer */
  dispose(): Promise<void>;
}

/** specklewidgets' defaults of the traits beside objects_gz */
function defaults(): Omit<GeoSpeckleViewerModel, "objects_gz"> {
  return {
    height: null,
    aspect_ratio: 16 / 9,
    selected: [],
    markers: [],
    object_count: 0,
    scene_bbox: [],
    ground_map: {},
    tilesets: [],
    surroundings: { ground_map: [], tiles: 0, hidden_features: 0, hidden_heights: [] },
  };
}

/**
 * GeoSpeckleViewer in el, on a page without a Python kernel: the widget specklewidgets runs in
 * a notebook, on a StaticModel that holds the traits. Without a ground_map and tilesets it is
 * specklewidgets' SpeckleViewer.
 */
export function mountGeoSpeckleViewer(
  el: HTMLElement,
  traits: GeoSpeckleViewerTraits,
): MountedGeoSpeckleViewer {
  const model = new StaticModel<GeoSpeckleViewerModel>({ ...defaults(), ...traits });
  // The widget reads only the model and its element
  const props = { model, el } as unknown as RenderProps<GeoSpeckleViewerModel>;
  const rendered = geospeckleViewer.render(props);
  return {
    model,
    loaded: rendered.then(() => undefined),
    async dispose() {
      (await rendered)();
    },
  };
}
