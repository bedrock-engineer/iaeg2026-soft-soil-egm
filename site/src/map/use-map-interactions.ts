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
  const layerId = feature.layer.id;

  if (layerId.endsWith("-clusters")) {
    const count = Number(feature.properties.point_count);
    return `<div class="text-xs">${nf.format(count)} location${count === 1 ? "" : "s"} — zoom in</div>`;
  }

  if (layerId.endsWith("-points") && layerId !== "model-cpt-points") {
    return tilePointHtml(feature);
  }

  if (layerId === "model-cpt-points") {
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

  if (layerId === "site-fill") {
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

/**
 * Unclustered PMTiles point: bro_id plus the attributes baked into
 * the tiles (quality regime, CPT quality class, final depth, report
 * year). Older records can miss any of them, so every line is
 * optional. Same content as bro-xml-app's popup.
 */
function tilePointHtml(feature: MapGeoJSONFeature): string {
  const properties = feature.properties;
  const metaLine = [asText(properties.quality), asText(properties.year)]
    .filter(Boolean)
    .join(" · ");
  const qualityClass = /^klasse(\d)$/.exec(asText(properties.quality_class));
  const depth = Number(properties.depth);

  const lines = [
    `<strong>${asText(properties.bro_id)}</strong>`,
    metaLine,
    qualityClass?.[1] ? `Quality class ${qualityClass[1]}` : "",
    Number.isFinite(depth) ? `Depth: ${depth} m` : "",
  ].filter(Boolean);

  return `<div class="text-xs">${lines.join("<br/>")}</div>`;
}

/**
 * Hover popups and pointer cursor for the overlays; clicking a cluster
 * zooms in on it.
 */
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

    const queryFeature = (event: MapMouseEvent) =>
      map.queryRenderedFeatures(event.point, { layers: interactiveLayers })[0];

    const handleMousemove = (event: MapMouseEvent) => {
      const feature = queryFeature(event);
      map.getCanvas().style.cursor = feature ? "pointer" : "";

      if (!feature) {
        popup.remove();
        return;
      }

      popup.setLngLat(event.lngLat).setHTML(popupHtml(feature)).addTo(map);
    };

    const handleClick = (event: MapMouseEvent) => {
      const feature = queryFeature(event);
      if (feature?.layer.id.endsWith("-clusters")) {
        // tippecanoe clusters are baked into the tiles; zooming in
        // reveals the underlying points
        const [lng = 0, lat = 0] = (feature.geometry as GeoJSON.Point)
          .coordinates;
        map.easeTo({ center: [lng, lat], zoom: map.getZoom() + 2 });
        return;
      }
      // Touch devices have no hover, so a tap shows the popup instead
      handleMousemove(event);
    };

    const handleMouseout = () => {
      popup.remove();
    };

    map.on("mousemove", handleMousemove);
    map.on("click", handleClick);
    map.on("mouseout", handleMouseout);

    return () => {
      popup.remove();
      map.off("mousemove", handleMousemove);
      map.off("click", handleClick);
      map.off("mouseout", handleMouseout);
    };
  }, [mapRef]);
}
