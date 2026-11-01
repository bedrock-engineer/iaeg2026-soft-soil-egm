import type { RenderProps } from "@anywidget/types";
import { mountSpeckleViewer } from "./lib/viewer";
import type { SpeckleViewerModel } from "./lib/types";

/**
 * Speckle's web viewer fed with v3 objects instead of a server URL. Each model in objects_gz
 * (its root first) loads through a MemoryLoader into its own subtree. After a load the
 * widget reports object_count and scene_bbox; a click selects an element (shift-click adds
 * to the selection, a click on nothing clears it) and reports it in selected.
 */
export default {
  async render({ model, el }: RenderProps<SpeckleViewerModel>) {
    const { dispose } = await mountSpeckleViewer(model, el);
    return dispose;
  },
};
