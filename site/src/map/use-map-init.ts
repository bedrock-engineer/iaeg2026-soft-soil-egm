import {
  Map as MaplibreMap,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type LngLatBoundsLike,
} from "maplibre-gl";
// MapLibre v6 resolves its worker via `new URL(..., import.meta.url)`,
// which Vite cannot rewrite, so point it at a Vite-bundled worker
// explicitly. Use `?worker&url` rather than plain `?url`: the dist
// worker imports its sibling maplibre-gl-shared.mjs, which only
// `?worker` bundles in.
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { type RefObject, useEffect, useRef, useState } from "react";
import { modelExtentBounds } from "../project-geometry";
import { createMapStyle, registerCptIcons } from "./map-style";
import { PortalControl } from "./portal-control";

setWorkerUrl(maplibreWorkerUrl);

const maxBounds: LngLatBoundsLike = [
  [2, 50],
  [8.5, 54.3],
];

interface MapInitResult {
  mapRef: RefObject<MaplibreMap | null>;
  /**
   * True once the style's initial `load` event has fired. The style is
   * never replaced (basemap switching only toggles layer visibility),
   * so this flips exactly once.
   */
  styleReady: boolean;
  /** Stable DOM node the layers panel renders into, null until mounted. */
  panel: HTMLDivElement | null;
}

export function useMapInit(
  containerRef: RefObject<HTMLDivElement | null>,
): MapInitResult {
  const mapRef = useRef<MaplibreMap | null>(null);
  const [panel, setPanel] = useState<HTMLDivElement | null>(null);
  const [styleReady, setStyleReady] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const map = new MaplibreMap({
      container,
      style: createMapStyle(),
      bounds: modelExtentBounds(),
      fitBoundsOptions: { padding: 48 },
      maxBounds,
      minZoom: 5,
      maxZoom: 19,
    });

    registerCptIcons(map);

    void map.once("load", () => {
      setStyleReady(true);
    });

    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new ScaleControl({ unit: "metric" }), "bottom-left");

    const panelControl = new PortalControl();
    map.addControl(panelControl, "top-left");

    mapRef.current = map;
    setPanel(panelControl.element);

    return () => {
      setPanel(null);
      setStyleReady(false);
      map.remove();
      mapRef.current = null;
    };
  }, [containerRef]);

  return { mapRef, styleReady, panel };
}
