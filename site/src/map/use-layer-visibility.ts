import type { Map as MaplibreMap } from "maplibre-gl";
import { type RefObject, useEffect, useState } from "react";
import { type Overlay, overlayLayerIds, overlays } from "./map-style";

interface LayerVisibilityResult {
  visibility: Record<Overlay, boolean>;
  setLayerVisible: (overlay: Overlay, visible: boolean) => void;
}

/**
 * Visibility toggles for the project overlays. Hidden layers are also
 * skipped by queryRenderedFeatures, so hover stops matching them too.
 */
export function useLayerVisibility(
  mapRef: RefObject<MaplibreMap | null>,
  styleReady: boolean,
): LayerVisibilityResult {
  const [visibility, setVisibility] = useState<Record<Overlay, boolean>>({
    extent: true,
    geotop: true,
    site: true,
    modelCpt: true,
    cpt: true,
    bhrgt: true,
    bhrg: true,
  });

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReady) {
      return;
    }
    for (const overlay of overlays) {
      const value = visibility[overlay] ? "visible" : "none";
      for (const layerId of overlayLayerIds[overlay]) {
        map.setLayoutProperty(layerId, "visibility", value);
      }
    }
  }, [mapRef, styleReady, visibility]);

  const setLayerVisible = (overlay: Overlay, visible: boolean) => {
    setVisibility((previous) => ({ ...previous, [overlay]: visible }));
  };

  return { visibility, setLayerVisible };
}
