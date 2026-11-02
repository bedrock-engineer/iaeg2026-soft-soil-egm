// The CrossSections widget's traits as the GeoBIM notebook sets them, apart from the widget so that
// scripts/check-soil.ts can check them in Node.
import type { Sample } from "./cpt-samples.ts";
import { type Grid, isKept, KEPT_ZONES, zoneColor, zoneLabel } from "./soil-model.ts";

const round3 = (value: number) => Math.round(value * 1000) / 1000;

export interface ValueScale {
  label: string;
  log: boolean;
  min: number;
  max: number;
  scheme: "viridis" | "oranges";
}

/** The widget's traits: the TS mirror of the notebook's */
export interface CrossSectionsModel {
  /** [x, y, z, unit, zone] per cell: its south-west corner, its center's z, indices into units and lithologies */
  voxels: number[][];
  cell: { x: number; y: number; z: number };
  units: Array<{ code: string; name: string; color: string }>;
  lithologies: Array<{ name: string; color: string }>;
  cpts: Array<{ bro_id: string; x: number; y: number; z: number[]; qc: number[] }>;
  domains: Array<{ name: string; color: string }>;
  /** An index into domains per cell, -1 where it is not simulated */
  domain_of: ArrayLike<number>;
  /** Rings of [x, y] in RD New */
  footprints: number[][][];
  color_modes: string[];
  color_by: "lithology" | "domain" | "value";
  /** float32 bytes per cell, null for none */
  values: DataView | null;
  value_scale: ValueScale | null;
  x: number;
  y: number;
  z: number;
  selected_cpt: string | null;
}

/**
 * The cells of the kept zones, as flat indices into the grid's arrays, and the widget's traits. The
 * samples are all of them, on simulated levels or not; the domains' colors are by their names.
 */
export function crossSectionTraits(
  grid: Grid,
  samples: Sample[],
  footprint: number[][],
  domainColors: Record<string, string>,
) {
  const [nx, ny] = [grid.x.length, grid.y.length];
  const { cell } = grid;
  const cells: number[] = [];
  const voxels: number[][] = [];
  grid.z.forEach((z, k) => {
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const index = (k * ny + j) * nx + i;
        const zone = grid.sbtnMostLikely[index];
        if (!isKept(zone)) {
          continue;
        }
        cells.push(index);
        voxels.push([
          round3(grid.x[i] - cell.x / 2),
          round3(grid.y[j] - cell.y / 2),
          round3(z),
          grid.stratigraphicUnit[index],
          KEPT_ZONES.indexOf(zone),
        ]);
      }
    }
  });

  // The CPTs' samples with a qc, from the top down
  const byCpt = new Map<string, CrossSectionsModel["cpts"][number]>();
  for (const sample of [...samples].sort((a, b) => b.z - a.z)) {
    if (sample.qc === null || !(sample.qc > 0)) {
      continue;
    }
    const cpt = byCpt.get(sample.bro_id) ?? { bro_id: sample.bro_id, x: sample.x, y: sample.y, z: [], qc: [] };
    byCpt.set(sample.bro_id, cpt);
    cpt.z.push(sample.z);
    cpt.qc.push(sample.qc);
  }
  const cpts = [...byCpt.values()].sort((a, b) => (a.bro_id < b.bro_id ? -1 : 1));

  // Where the sections start: through the cell under the building's centroid, at the level nearest the
  // median sample, and with the CPT nearest the building
  const [cx, cy] = centroid(footprint);
  const at = (value: number, centers: Float64Array, size: number) =>
    round3(centers[0] - size / 2 + Math.floor((value - (centers[0] - size / 2)) / size) * size);
  const zs = cpts.flatMap((cpt) => cpt.z).sort((a, b) => a - b);
  const middle = zs.length >> 1;
  const median = zs.length % 2 ? zs[middle] : (zs[middle - 1] + zs[middle]) / 2;
  const levels = [...new Set(voxels.map((voxel) => voxel[2]))];
  const level = levels.reduce((best, z) => (Math.abs(z - median) < Math.abs(best - median) ? z : best));
  const nearest = cpts.reduce((best, cpt) =>
    Math.hypot(cpt.x - cx, cpt.y - cy) < Math.hypot(best.x - cx, best.y - cy) ? cpt : best,
  );

  const traits: CrossSectionsModel = {
    voxels,
    cell,
    units: grid.units.map((code) => ({ code, name: code, color: "#cccccc" })),
    lithologies: KEPT_ZONES.map((zone) => ({ name: zoneLabel(zone), color: zoneColor(zone) })),
    cpts,
    domains: grid.domains.map((name) => ({ name, color: domainColors[name] })),
    domain_of: Int8Array.from(cells, (index) => grid.domain[index]),
    footprints: [footprint],
    color_modes: [],
    color_by: "lithology",
    values: null,
    value_scale: null,
    x: at(cx, grid.x, cell.x),
    y: at(cy, grid.y, cell.y),
    z: level,
    selected_cpt: nearest?.bro_id ?? null,
  };
  return { cells, traits };
}

/** A ring's centroid */
function centroid(ring: number[][]): [number, number] {
  let [area, x, y] = [0, 0, 0];
  ring.forEach(([x0, y0], i) => {
    const [x1, y1] = ring[(i + 1) % ring.length];
    const cross = x0 * y1 - x1 * y0;
    area += cross;
    x += (x0 + x1) * cross;
    y += (y0 + y1) * cross;
  });
  return [x / (3 * area), y / (3 * area)];
}

/** The value at fraction q of the finite values, interpolated linearly, as numpy's percentile */
export function quantile(values: Float32Array, q: number): number {
  const sorted = values.filter(Number.isFinite).sort();
  const position = (sorted.length - 1) * q;
  const below = Math.floor(position);
  return sorted[below] + (sorted[Math.min(below + 1, sorted.length - 1)] - sorted[below]) * (position - below);
}
