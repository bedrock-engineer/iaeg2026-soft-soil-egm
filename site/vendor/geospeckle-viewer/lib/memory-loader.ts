import { ObjectLoader2Factory, type ObjectLoader2 } from "@speckle/objectloader2";
import { SpeckleLoader, type WorldTree } from "@speckle/viewer";
import type { SpeckleObject } from "./types";

/** objectloader2's own object type, which its index does not export */
type Base = Parameters<typeof ObjectLoader2Factory.createFromObjects>[0][number];

/**
 * A SpeckleLoader that reads objects from memory instead of a Speckle server: it hands them
 * to ObjectLoader2Factory.createFromObjects, the in-memory object loader. The viewer's own
 * SpeckleOfflineLoader would be the obvious choice, but in 2.31.14 it ignores the objects it
 * is given. The resource, which names the model's subtree in the viewer, is
 * `memory/<root id>`.
 */
export class MemoryLoader extends SpeckleLoader {
  constructor(tree: WorldTree, objects: SpeckleObject[]) {
    // SpeckleLoader's constructor calls initObjectLoader, before this class's fields exist,
    // so the objects go through as its resourceData
    super(tree, `memory/${objects[0].id}`, undefined, undefined, objects);
  }

  protected override initObjectLoader(
    _resource: string,
    _authToken?: string,
    _enableCaching?: boolean,
    resourceData?: unknown,
  ): ObjectLoader2 {
    return ObjectLoader2Factory.createFromObjects(resourceData as Base[]);
  }
}
