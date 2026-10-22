import type {
  LayerSpecification,
  Map as MaplibreMap,
  StyleSpecification,
} from "maplibre-gl";
import {
  cptGeoJSON,
  modelExtentGeoJSON,
  sitePlotGeoJSON,
} from "../project-geometry";

const kadasterAttribution =
  'Kaartgegevens &copy; <a href="https://www.kadaster.nl/">Kadaster</a>';

interface BasemapDefinition {
  id: string;
  label: string;
  tiles: string;
  attribution: string;
}

// The same basemaps as bro-xml-app
export const basemaps: ReadonlyArray<BasemapDefinition> = [
  {
    id: "brt",
    label: "Topographic",
    tiles:
      "https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/standaard/EPSG:3857/{z}/{x}/{y}.png",
    attribution: kadasterAttribution,
  },
  {
    id: "luchtfoto",
    label: "Aerial photo",
    tiles:
      "https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg",
    attribution: kadasterAttribution,
  },
  {
    id: "osm",
    label: "OpenStreetMap",
    tiles: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
];

export type BasemapId = string;

export const defaultBasemapId: BasemapId = "luchtfoto";

export const overlayColors = {
  extent: "#f59e0b", // amber
  site: "#dc2626", // red
  cpt: "#2563eb", // blue, the bro-xml-app CPT color
};

/** The project overlays, each toggled as a group of layers. */
export type Overlay = keyof typeof overlayColors;

export const overlayLayerIds: Record<Overlay, Array<string>> = {
  extent: ["extent-fill", "extent-line"],
  site: ["site-fill", "site-line"],
  cpt: ["cpt-points"],
};

export const overlays = Object.keys(overlayColors) as Array<Overlay>;

export const interactiveLayers = ["cpt-points", "site-fill", "extent-fill"];

interface MapIcon {
  data: ImageData;
  pixelRatio: number;
}

/**
 * Downward-pointing triangle (the geotechnical map convention for a
 * cone penetration test), rendered at 2x for crisp display.
 */
function triangleIcon(
  size: number,
  color: string,
  strokeWidth: number,
  strokeColor: string,
): MapIcon {
  const pixelRatio = 2;
  const canvas = document.createElement("canvas");
  canvas.width = size * pixelRatio;
  canvas.height = size * pixelRatio;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("Canvas 2D context unavailable");
  }

  context.scale(pixelRatio, pixelRatio);

  const inset = strokeWidth / 2 + 0.5;

  context.beginPath();
  context.moveTo(inset, inset);
  context.lineTo(size - inset, inset);
  context.lineTo(size / 2, size - inset);
  context.closePath();
  context.fillStyle = color;
  context.fill();
  context.lineJoin = "round";
  context.lineWidth = strokeWidth;
  context.strokeStyle = strokeColor;
  context.stroke();

  return {
    data: context.getImageData(0, 0, canvas.width, canvas.height),
    pixelRatio,
  };
}

export function registerCptIcons(map: MaplibreMap): void {
  const icon = triangleIcon(14, overlayColors.cpt, 1.5, "#ffffff");
  map.addImage("cpt-triangle", icon.data, { pixelRatio: icon.pixelRatio });
}

const overlayLayers: Array<LayerSpecification> = [
  {
    id: "extent-fill",
    type: "fill",
    source: "extent",
    paint: { "fill-color": overlayColors.extent, "fill-opacity": 0.08 },
  },
  {
    id: "extent-line",
    type: "line",
    source: "extent",
    paint: {
      "line-color": overlayColors.extent,
      "line-width": 2.5,
      "line-dasharray": [3, 2],
    },
  },
  {
    id: "site-fill",
    type: "fill",
    source: "site",
    paint: { "fill-color": overlayColors.site, "fill-opacity": 0.25 },
  },
  {
    id: "site-line",
    type: "line",
    source: "site",
    paint: { "line-color": overlayColors.site, "line-width": 2 },
  },
  {
    id: "cpt-points",
    type: "symbol",
    source: "cpts",
    layout: {
      "icon-image": "cpt-triangle",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  },
];

export function createMapStyle(): StyleSpecification {
  // All basemaps are part of the style; switching toggles layer
  // visibility instead of adding/removing sources.
  const basemapSources = Object.fromEntries(
    basemaps.map((definition) => [
      `basemap-${definition.id}`,
      {
        type: "raster" as const,
        tiles: [definition.tiles],
        tileSize: 256,
        maxzoom: 19,
        attribution: definition.attribution,
      },
    ]),
  );

  const basemapLayers: StyleSpecification["layers"] = basemaps.map(
    (definition) => ({
      id: `basemap-${definition.id}`,
      type: "raster",
      source: `basemap-${definition.id}`,
      layout: {
        visibility: definition.id === defaultBasemapId ? "visible" : "none",
      },
    }),
  );

  return {
    version: 8,
    sources: {
      ...basemapSources,
      extent: { type: "geojson", data: modelExtentGeoJSON() },
      site: { type: "geojson", data: sitePlotGeoJSON() },
      cpts: {
        type: "geojson",
        data: cptGeoJSON(),
        attribution: "BRO",
      },
    },
    layers: [...basemapLayers, ...overlayLayers],
  };
}
