import "maplibre-gl/dist/maplibre-gl.css";
import { useRef } from "react";
import { createPortal } from "react-dom";
import { MapLayersPanel } from "./map-controls";
import { useBasemap } from "./use-basemap";
import { useLayerVisibility } from "./use-layer-visibility";
import { useMapInit } from "./use-map-init";
import { useMapInteractions } from "./use-map-interactions";

/**
 * The bro-xml-app map, reduced to its basemaps and layers panel, with
 * the project overlays: the GeoTOP model extent, the site plot and the
 * BRO CPTs inside the extent, on top of the BRO locations PMTiles.
 */
export function ProjectMap({ footprint }: { footprint: GeoJSON.Feature<GeoJSON.Polygon> }) {
  const containerRef = useRef<HTMLDivElement>(null);

  const { mapRef, styleReady, panel } = useMapInit(containerRef, footprint);

  useMapInteractions(mapRef);

  const [basemap, setBasemap] = useBasemap(mapRef, styleReady);

  const { visibility, setLayerVisible } = useLayerVisibility(
    mapRef,
    styleReady,
  );

  return (
    <>
      <div
        ref={containerRef}
        className="project-map"
      />

      {panel &&
        createPortal(
          <MapLayersPanel
            visibility={visibility}
            onVisibilityChange={setLayerVisible}
            basemap={basemap}
            onBasemapChange={setBasemap}
          />,
          panel,
        )}
    </>
  );
}
