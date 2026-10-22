import {
  addProtocol,
  type FilterSpecification,
  type LayerSpecification,
  type Map as MaplibreMap,
  type StyleSpecification,
} from "maplibre-gl";
import { Protocol } from "pmtiles";
import {
  cptGeoJSON,
  cptRecords,
  modelExtentGeoJSON,
  sitePlotGeoJSON,
} from "../project-geometry";

// Register the PMTiles protocol once per app load
const protocol = new Protocol();
addProtocol("pmtiles", protocol.tile);

/** The BRO locations PMTiles that bro-xml-app also uses. */
const broPmtilesUrl = "https://r2.eu.bedrock.engineer/bro_locations.pmtiles";

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

// The bro-xml-app colors: tile points by type, and violet with a dark
// ring for highlighted points (there: files loaded in the app; here:
// the CPTs inside the model extent).
export const overlayColors = {
  extent: "#f59e0b", // amber
  site: "#dc2626", // red
  modelCpt: "#7c3aed", // violet
  cpt: "#2563eb", // blue
  bhrgt: "#ea580c", // orange
  bhrg: "#16a34a", // green
};

const highlightStrokeColor = "#1f2937";

/** The BRO PMTiles source layers, in draw order. */
export const broTileLayers = ["cpt", "bhrgt", "bhrg"] as const;

type BROLocationLayer = (typeof broTileLayers)[number];

export function pointLayerId(layer: BROLocationLayer): string {
  return `${layer}-points`;
}

export function clusterLayerId(layer: BROLocationLayer): string {
  return `${layer}-clusters`;
}

/** The map overlays, each toggled as a group of layers. */
export type Overlay = keyof typeof overlayColors;

export const overlayLayerIds: Record<Overlay, Array<string>> = {
  extent: ["extent-fill", "extent-line"],
  site: ["site-fill", "site-line"],
  modelCpt: ["model-cpt-points"],
  cpt: [pointLayerId("cpt"), clusterLayerId("cpt")],
  bhrgt: [pointLayerId("bhrgt"), clusterLayerId("bhrgt")],
  bhrg: [pointLayerId("bhrg"), clusterLayerId("bhrg")],
};

export const overlays = Object.keys(overlayColors) as Array<Overlay>;

// Layers that respond to hover/click, in priority order: model CPTs
// first, then single BRO points, clusters, and the project areas
export const interactiveLayers = [
  "model-cpt-points",
  ...broTileLayers.map((layer) => pointLayerId(layer)),
  ...broTileLayers.map((layer) => clusterLayerId(layer)),
  "site-fill",
  "extent-fill",
];

/**
 * Filter for the unclustered tile point layers. The model CPTs are
 * excluded so each of them renders exactly once, as its highlighted
 * marker. Clusters are baked into the tiles by tippecanoe, so their
 * counts still include them.
 */
const broPointFilter: FilterSpecification = [
  "all",
  ["!", ["has", "point_count"]],
  [
    "!",
    ["in", ["get", "bro_id"], ["literal", cptRecords.map((cpt) => cpt.bro_id)]],
  ],
];

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

/**
 * Register the CPT triangle icons: small for tile points, larger for
 * the model CPTs.
 */
export function registerCptIcons(map: MaplibreMap): void {
  const icons: Record<string, MapIcon> = {
    "cpt-triangle": triangleIcon(12, overlayColors.cpt, 1.5, "#ffffff"),
    "cpt-triangle-model": triangleIcon(
      18,
      overlayColors.modelCpt,
      2,
      highlightStrokeColor,
    ),
  };

  for (const [id, icon] of Object.entries(icons)) {
    map.addImage(id, icon.data, { pixelRatio: icon.pixelRatio });
  }
}

/**
 * Single unclustered points: CPTs draw as triangle symbols (see
 * `registerCptIcons`), boreholes as circles.
 */
function broPointLayer(layer: BROLocationLayer): LayerSpecification {
  if (layer === "cpt") {
    return {
      id: pointLayerId(layer),
      type: "symbol",
      source: "bro",
      "source-layer": layer,
      filter: broPointFilter,
      layout: {
        "icon-image": "cpt-triangle",
        "icon-allow-overlap": true,
        "icon-ignore-placement": true,
      },
      paint: {
        "icon-opacity": 0.85,
      },
    };
  }

  return {
    id: pointLayerId(layer),
    type: "circle",
    source: "bro",
    "source-layer": layer,
    filter: broPointFilter,
    paint: {
      "circle-color": overlayColors[layer],
      "circle-opacity": 0.85,
      "circle-radius": 4,
      "circle-stroke-width": 1,
      "circle-stroke-color": "#ffffff",
    },
  };
}

/**
 * Layers for one source-layer of the BRO locations PMTiles: one circle
 * layer for clusters (sized by point_count), one for single points.
 * Clusters carry `point_count`; only single points have a usable bro_id.
 */
function broLocationLayers(layer: BROLocationLayer): Array<LayerSpecification> {
  return [
    {
      id: clusterLayerId(layer),
      type: "circle",
      source: "bro",
      "source-layer": layer,
      filter: ["has", "point_count"],
      paint: {
        "circle-color": overlayColors[layer],
        "circle-opacity": 0.5,
        // Radius follows sqrt(count) so circle area is proportional
        // to the number of points; counts range from 2 to ~50k.
        // prettier-ignore
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["sqrt", ["get", "point_count"]],
          // sqrt of count, radius
          1.4, 5,
          7, 9,
          22, 11,
          71, 13,
          225, 20,
        ],
        "circle-stroke-width": 1,
        "circle-stroke-color": "#ffffff",
      },
    },
    broPointLayer(layer),
  ];
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
  ...broTileLayers.flatMap((layer) => broLocationLayers(layer)),
  {
    id: "model-cpt-points",
    type: "symbol",
    source: "cpts",
    layout: {
      "icon-image": "cpt-triangle-model",
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
      bro: {
        type: "vector",
        url: `pmtiles://${broPmtilesUrl}`,
        attribution: "BRO",
      },
      cpts: { type: "geojson", data: cptGeoJSON() },
    },
    layers: [...basemapLayers, ...overlayLayers],
  };
}
