import type { Feature, FeatureCollection, MultiPolygon, Point, Polygon, Position } from "geojson";
import {
  type FilterSpecification,
  type GeoJSONSource,
  LngLatBounds,
  Map as MaplibreMap,
  NavigationControl,
  type RasterSourceSpecification,
  ScaleControl,
  setWorkerUrl,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

// MapLibre looks for its worker next to its own module, which the page's bundle is not
setWorkerUrl(workerUrl);

import { type Footprints, selectedFootprints } from "./footprints";

export { type FootprintProperties, type Footprints, selectedFootprints } from "./footprints";

const KADASTER = '<a href="https://www.kadaster.nl/">Kadaster</a> / PDOK';

/** PDOK's basemaps, as bro-xml-app and the IAEG demo have them */
export const BASEMAPS = {
  aerial: {
    type: "raster",
    tiles: [
      "https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg",
    ],
    tileSize: 256,
    maxzoom: 19,
    attribution: `Luchtfoto &copy; ${KADASTER}`,
  },
  topographic: {
    type: "raster",
    tiles: [
      "https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/standaard/EPSG:3857/{z}/{x}/{y}.png",
    ],
    tileSize: 256,
    maxzoom: 19,
    attribution: `BRT-Achtergrondkaart &copy; ${KADASTER}`,
  },
} satisfies Record<string, RasterSourceSpecification>;

export type Basemap = keyof typeof BASEMAPS;

/** The basemap the map opens on; index.html's pressed button says the same */
export const DEFAULT_BASEMAP: Basemap = "topographic";

const COLORS = {
  outline: "#e3262b",
  storey: "#9cc3ff",
  selected: "#2f6fde",
};

/** [west, south, east, north] of a feature's coordinates */
function bounds(features: Feature<Polygon | MultiPolygon>[]): LngLatBounds | null {
  const box = new LngLatBounds();
  let empty = true;
  for (const { geometry } of features) {
    const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
    for (const ring of polygons.flat()) {
      for (const [lng, lat] of ring) {
        box.extend([lng, lat]);
        empty = false;
      }
    }
  }
  return empty ? null : box;
}

/** The middle of a feature's bounds: where the ring around a small footprint goes */
function middle(feature: Feature<Polygon | MultiPolygon>): Position {
  return (bounds([feature]) as LngLatBounds).getCenter().toArray();
}

const NO_FOOTPRINTS: Footprints = { type: "FeatureCollection", features: [] };

/**
 * A MapLibre map of a model's footprints on PDOK's topographic map: the building's outline
 * dotted red, and for a selection its footprints filled, with a ring around each so that a column's half
 * meter stands out, and the other footprints of their storeys faint. It opens on the building's
 * bounds alone, so that it moves before the outline (setOutline) and the footprints (setFootprints)
 * are in.
 */
export class FootprintMap {
  readonly map: MaplibreMap;
  #footprints = NO_FOOTPRINTS;
  #outline: FeatureCollection = NO_FOOTPRINTS;
  #ids: string[] = [];

  constructor(container: HTMLElement, home: [number, number, number, number]) {
    this.map = new MaplibreMap({
      container,
      style: {
        version: 8,
        sources: {
          ...BASEMAPS,
          outline: { type: "geojson", data: NO_FOOTPRINTS },
          footprints: { type: "geojson", data: NO_FOOTPRINTS },
          rings: { type: "geojson", data: { type: "FeatureCollection", features: [] } },
        },
        layers: [
          ...Object.keys(BASEMAPS).map((basemap) => ({
            id: basemap,
            type: "raster" as const,
            source: basemap,
            layout: {
              visibility: basemap === DEFAULT_BASEMAP ? ("visible" as const) : ("none" as const),
            },
          })),
          {
            id: "storey-fill",
            type: "fill",
            source: "footprints",
            filter: ["boolean", false],
            paint: { "fill-color": COLORS.storey, "fill-opacity": 0.15 },
          },
          {
            id: "storey-line",
            type: "line",
            source: "footprints",
            filter: ["boolean", false],
            paint: { "line-color": COLORS.storey, "line-width": 1 },
          },
          {
            id: "outline",
            type: "line",
            source: "outline",
            // Dots: dashes of no length with round caps, a dot's width apart
            layout: { "line-cap": "round", "line-join": "round" },
            paint: { "line-color": COLORS.outline, "line-width": 3, "line-dasharray": [0, 2] },
          },
          {
            id: "selected-fill",
            type: "fill",
            source: "footprints",
            filter: ["boolean", false],
            paint: { "fill-color": COLORS.selected, "fill-opacity": 0.75 },
          },
          {
            id: "selected-line",
            type: "line",
            source: "footprints",
            filter: ["boolean", false],
            paint: { "line-color": COLORS.selected, "line-width": 2 },
          },
          {
            id: "rings",
            type: "circle",
            source: "rings",
            paint: {
              "circle-radius": 14,
              "circle-color": "rgba(0, 0, 0, 0)",
              "circle-stroke-color": COLORS.selected,
              "circle-stroke-width": 3,
            },
          },
        ],
      },
      bounds: home,
      fitBoundsOptions: { padding: 40 },
      maxZoom: 22,
      // Turn, never tilt (joost): a right-drag, Ctrl-drag or pinch turns the map; no drag,
      // two-finger swipe or Shift+arrow can pitch it, as maxPitch 0 holds whatever asks
      maxPitch: 0,
      pitchWithRotate: false,
      touchPitch: false,
    });
    this.map.addControl(new NavigationControl({ showCompass: true }), "top-left");
    this.map.addControl(new ScaleControl({ unit: "metric" }), "bottom-left");
  }

  /** The building's outline, once it is in */
  setOutline(outline: FeatureCollection) {
    this.#outline = outline;
    this.#styled(() => (this.map.getSource("outline") as GeoJSONSource).setData(outline));
  }

  /** The models' footprints, once they are in; a selection made before shows on them */
  setFootprints(footprints: Footprints) {
    this.#footprints = footprints;
    this.#styled(() => {
      (this.map.getSource("footprints") as GeoJSONSource).setData(footprints);
      if (this.#ids.length) {
        this.select(this.#ids);
      }
    });
  }

  /** Runs apply once the map has its sources, which it takes a frame after it is made */
  #styled(apply: () => void) {
    if (this.map.getSource("footprints")) {
      apply();
    } else {
      this.map.once("style.load", apply);
    }
  }

  /** Shows one of the BASEMAPS */
  setBasemap(basemap: Basemap) {
    for (const layer of Object.keys(BASEMAPS)) {
      this.map.setLayoutProperty(layer, "visibility", layer === basemap ? "visible" : "none");
    }
  }

  /**
   * Shows the footprints of the elements with these ids and goes to them; none goes back to
   * the whole building.
   *
   * @returns the selected footprints and their storeys
   */
  select(ids: string[]) {
    this.#ids = ids;
    const { features, storeys } = selectedFootprints(this.#footprints, ids);
    const ofIds: FilterSpecification = ["in", ["get", "id"], ["literal", ids]];
    const onStoreys: FilterSpecification = [
      "all",
      ["in", ["get", "storey"], ["literal", storeys]],
      ["!", ofIds],
    ];
    for (const layer of ["storey-fill", "storey-line"]) {
      this.map.setFilter(layer, onStoreys);
    }
    for (const layer of ["selected-fill", "selected-line"]) {
      this.map.setFilter(layer, ofIds);
    }
    const rings: FeatureCollection<Point> = {
      type: "FeatureCollection",
      features: features.map((feature) => ({
        type: "Feature",
        properties: {},
        geometry: { type: "Point", coordinates: middle(feature) },
      })),
    };
    (this.map.getSource("rings") as GeoJSONSource).setData(rings);
    const target =
      bounds(features) ?? bounds(this.#outline.features as Feature<Polygon | MultiPolygon>[]);
    if (target) {
      const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      // A column's half meter at most 20: some of its storey stays in view around it
      this.map.fitBounds(target, { padding: 60, maxZoom: 20, duration: still ? 0 : 600 });
    }
    return { features, storeys };
  }

  /** The ids of the selected footprints that the map draws now */
  drawnSelection(): string[] {
    const drawn = this.map.queryRenderedFeatures({ layers: ["selected-fill"] });
    return [...new Set(drawn.map((feature) => feature.properties.id as string))].filter((id) =>
      this.#ids.includes(id),
    );
  }
}
