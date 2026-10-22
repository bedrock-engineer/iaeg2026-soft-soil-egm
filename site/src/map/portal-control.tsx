import type { IControl } from "maplibre-gl";

export function swallowEvent(event: Event) {
  event.stopPropagation();
}

/**
 * Generic MapLibre IControl that hands back a stable DOM element so a
 * React subtree can render into it via `createPortal`. All behaviour
 * lives in the React tree; this exists purely because MapLibre's
 * IControl contract demands an HTMLElement.
 *
 * MapLibre's pointer interactions (pan, zoom, double-click-to-zoom,
 * scroll-wheel) fire on the map canvas; stop-propagation listeners keep
 * gestures on the hosted widgets from leaking through to the map.
 *
 * Ported from bedrock-engineer/bro-xml-app.
 */
export class PortalControl implements IControl {
  readonly element: HTMLDivElement;

  constructor() {
    const element = document.createElement("div");
    element.className = "maplibregl-ctrl";
    element.addEventListener("mousedown", swallowEvent);
    element.addEventListener("pointerdown", swallowEvent);
    element.addEventListener("dblclick", swallowEvent);
    element.addEventListener("wheel", swallowEvent);
    this.element = element;
  }

  onAdd(): HTMLElement {
    return this.element;
  }

  onRemove(): void {
    this.element.remove();
  }
}
