import type { FeatureCollection, MultiPolygon, Polygon } from "geojson";

// Apart from footprint-map.ts, so that the page can describe a selection without loading MapLibre, which
// it leaves out on a phone

/** What site/sixty5.py writes for each footprint: the row's id, class, name and storey */
export interface FootprintProperties {
  id: string;
  class: string | null;
  name: string | null;
  storey: string | null;
  /** The storey's elevation in meters, in the model's height system */
  elevation: number | null;
}

export type Footprints = FeatureCollection<Polygon | MultiPolygon, FootprintProperties>;

/** The footprints of the given ids and the storeys they are on */
export function selectedFootprints(footprints: Footprints, ids: string[]) {
  const wanted = new Set(ids);
  const features = footprints.features.filter((feature) => wanted.has(feature.properties.id));
  const storeys = [
    ...new Set(features.map((feature) => feature.properties.storey).filter((s) => s !== null)),
  ];
  return { features, storeys };
}
