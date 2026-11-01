import { elementOf, type NodeLike } from "./selection";
import type { SpeckleObject } from "./types";

/** A three.js Box3, as far as the bbox trait needs it */
export interface BoxLike {
  min: { x: number; y: number; z: number };
  max: { x: number; y: number; z: number };
  isEmpty(): boolean;
}

/** [xmin, ymin, zmin, xmax, ymax, zmax] of a box, [] for an empty one */
export function bboxList(box: BoxLike): number[] {
  if (box.isEmpty()) {
    return [];
  }
  return [box.min.x, box.min.y, box.min.z, box.max.x, box.max.y, box.max.z];
}

/** A viewer tree node: the part of tree-model's node that the count needs */
export interface TreeNodeLike extends NodeLike {
  model: NodeLike["model"] & { atomic?: boolean; renderView?: unknown };
  parent?: TreeNodeLike | null;
}

/**
 * The elements the viewer draws: what a click on each drawn piece of geometry selects. The
 * viewer picks a piece's nearest atomic ancestor (an object with a displayValue); the widget
 * then takes the instance that places it (elementOf). So an element with several meshes counts
 * once, and an instance once per placement.
 *
 * @param nodes the viewer's tree nodes, each instance placement its own node
 * @param drawn the render views in the viewer's batches
 */
export function drawnElements(
  nodes: TreeNodeLike[],
  drawn: Set<unknown>,
  placedBy: Map<string, SpeckleObject>,
): Set<Record<string, unknown>> {
  const elements = new Set<Record<string, unknown>>();
  for (let node of nodes) {
    if (!drawn.has(node.model.renderView)) {
      continue;
    }
    while (!node.model.atomic && node.parent) {
      node = node.parent;
    }
    elements.add(elementOf(node, placedBy));
  }
  return elements;
}
