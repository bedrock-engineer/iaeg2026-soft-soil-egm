import type {
  MapGeoJSONFeature,
  Map as MaplibreMap,
  MapMouseEvent,
} from "maplibre-gl";
import { Popup } from "maplibre-gl";
import { type RefObject, useEffect } from "react";
import { modelExtent } from "../project-geometry";
import { interactiveLayers } from "./map-style";

const nf = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });

// String(undefined) is the truthy "undefined", so keep absent values empty
function asText(value: unknown): string {
  return value == null ? "" : String(value);
}

function popupHtml(feature: MapGeoJSONFeature): string {
  if (feature.layer.id === "cpt-points") {
    const properties = feature.properties;
    const base = Number(properties.z_base_nap);
    const lines = [
      `<strong>${asText(properties.bro_id)}</strong>`,
      `RD ${nf.format(Number(properties.x))}, ${nf.format(Number(properties.y))}`,
      Number.isFinite(base) ? `Base: ${base.toFixed(1)} m NAP` : "",
      properties.deepest_unit
        ? `Deepest GeoTOP unit: ${asText(properties.deepest_unit)}`
        : "",
      asText(properties.date),
    ].filter(Boolean);
    return `<div class="text-xs">${lines.join("<br/>")}</div>`;
  }

  if (feature.layer.id === "site-fill") {
    return `<div class="text-xs"><strong>Site plot</strong><br/>Fictitious building plot</div>`;
  }

  const { xmin, xmax, ymin, ymax, zmin } = modelExtent;
  return `<div class="text-xs">
    <strong>GeoTOP model extent</strong><br/>
    x ${nf.format(xmin)} – ${nf.format(xmax)}<br/>
    y ${nf.format(ymin)} – ${nf.format(ymax)}<br/>
    ${xmax - xmin} × ${ymax - ymin} m, down to ${zmin} m NAP
  </div>`;
}

/** Hover popups and pointer cursor for the project overlays. */
export function useMapInteractions(
  mapRef: RefObject<MaplibreMap | null>,
): void {
  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const popup = new Popup({
      closeButton: false,
      closeOnClick: false,
      maxWidth: "260px",
    });

    const handleMousemove = (event: MapMouseEvent) => {
      const feature = map.queryRenderedFeatures(event.point, {
        layers: interactiveLayers,
      })[0];
      map.getCanvas().style.cursor = feature ? "pointer" : "";

      if (!feature) {
        popup.remove();
        return;
      }

      popup.setLngLat(event.lngLat).setHTML(popupHtml(feature)).addTo(map);
    };

    const handleMouseout = () => {
      popup.remove();
    };

    // Touch devices have no hover, so a tap shows the same popup
    map.on("mousemove", handleMousemove);
    map.on("click", handleMousemove);
    map.on("mouseout", handleMouseout);

    return () => {
      popup.remove();
      map.off("mousemove", handleMousemove);
      map.off("click", handleMousemove);
      map.off("mouseout", handleMouseout);
    };
  }, [mapRef]);
}
