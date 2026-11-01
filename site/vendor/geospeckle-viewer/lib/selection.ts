import type { SpeckleObject } from "./types";

/** The part of a viewer tree node that selection needs: tree-model's node shape */
export interface NodeLike {
  model: { raw: Record<string, unknown> };
  parent?: NodeLike | null;
}

const INSTANCE_PROXY = "InstanceProxy";

function isInstanceProxy(raw: Record<string, unknown> | undefined): boolean {
  return typeof raw?.speckle_type === "string" && raw.speckle_type.endsWith(INSTANCE_PROXY);
}

/**
 * The definition members placed exactly once, mapped to the InstanceProxy that places them.
 * The viewer draws such an instance as its definition's own objects (it batches only
 * repeated geometry), so a click on it lands on a member rather than under the proxy.
 * Members are applicationIds, which models_gz namespaces per model, so the maps of several
 * models can be merged.
 */
export function singlePlacements(objects: SpeckleObject[]): Map<string, SpeckleObject> {
  const placements = new Map<string, SpeckleObject[]>();
  for (const object of objects) {
    if (isInstanceProxy(object) && typeof object.definitionId === "string") {
      placements.set(object.definitionId, [...(placements.get(object.definitionId) ?? []), object]);
    }
  }
  const placedBy = new Map<string, SpeckleObject>();
  const definitions = (objects[0]?.instanceDefinitionProxies ?? []) as SpeckleObject[];
  for (const definition of definitions) {
    const placed = placements.get(definition.applicationId ?? "") ?? [];
    if (placed.length !== 1) {
      continue;
    }
    for (const member of (definition.objects ?? []) as string[]) {
      placedBy.set(member, placed[0]);
    }
  }
  return placedBy;
}

/**
 * The element a selected node belongs to. An instance drawn as instanced geometry hangs under
 * its InstanceProxy; one drawn as its definition's objects is found in placedBy. Nested
 * instances resolve to the outermost InstanceProxy.
 */
export function elementOf(node: NodeLike, placedBy: Map<string, SpeckleObject>) {
  let element = node.model.raw;
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (isInstanceProxy(parent.model?.raw)) {
      element = parent.model.raw;
    }
  }
  // A placed member can itself be a nested instance's member: follow the chain, bounded in
  // case a model's definitions refer to each other
  for (let depth = 0; depth < 16; depth++) {
    const placement = placedBy.get(element.applicationId as string);
    if (!placement) {
      break;
    }
    element = placement;
  }
  return element;
}

/** Geometry and child references, left out of the selected objects sent to Python */
const NOT_SELECTED = new Set(["displayValue", "elements", "__closure"]);

/** The selected elements as plain JSON for the `selected` trait, each element once */
export function selectionData(elements: Record<string, unknown>[]): Record<string, unknown>[] {
  const unique = [...new Set(elements)];
  return JSON.parse(
    JSON.stringify(unique, (key, value) => (NOT_SELECTED.has(key) ? undefined : value)),
  );
}
