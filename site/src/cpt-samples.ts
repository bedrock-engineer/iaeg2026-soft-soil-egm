// The CPTs' samples at the cells' height, classified with `robertson` as the notebooks classify them
// (06_bimdataframes.py, from 03_variograms.py's samples): the median qc and fs of the readings in each
// sample, on the levels of the cells, with the ground at the top of the cells' column.
import { asyncBufferFromUrl, parquetReadObjects } from "hyparquet";
import { compressors } from "hyparquet-compressors";
import { robertson } from "./robertson.ts";
import { type Grid, SOIL_MODEL_URL } from "./soil-model.ts";

/** m, GeoTOP's columns and the height of its voxels, which the samples are counted in */
const COLUMN = 100;
const VOXEL = 0.5;

/** One reading of cpts.parquet: qc and fs in MPa, z in m NAP */
export interface Reading {
  bro_id: string;
  x: number;
  y: number;
  z: number;
  qc: number | null;
  fs: number | null;
}

export interface Sample {
  bro_id: string;
  x: number;
  y: number;
  /** The sample's center, m NAP */
  z: number;
  /** The GeoTOP column it lies in: its south-west corner */
  column_x: number;
  column_y: number;
  /** The median of its readings, null without any */
  qc: number | null;
  fs: number | null;
}

/** A usable sample (qc and fs above 0) on a simulated level, with its classification */
export interface ClassifiedSample extends Sample {
  zone: number;
  ic: number;
}

export async function readReadings(): Promise<Reading[]> {
  const file = await asyncBufferFromUrl({ url: `${SOIL_MODEL_URL}cpts.parquet` });
  return (await parquetReadObjects({
    file,
    columns: ["bro_id", "x", "y", "z", "qc", "fs"],
    compressors,
  })) as Reading[];
}

/** Polars' round, which rounds halves to even: 03_variograms.py's samples were counted with it */
function roundHalfEven(value: number): number {
  const floor = Math.floor(value);
  const rest = value - floor;
  if (rest !== 0.5) {
    return Math.round(value);
  }
  return floor % 2 === 0 ? floor : floor + 1;
}

const round3 = (value: number) => Math.round(value * 1000) / 1000;

/** The median of the values that are there, as polars takes it; null without any */
function median(values: Array<number | null>): number | null {
  const sorted = values.filter((v): v is number => v !== null && !Number.isNaN(v)).sort((a, b) => a - b);
  if (!sorted.length) {
    return null;
  }
  const middle = sorted.length >> 1;
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

/**
 * The readings in samples of height h: per CPT, GeoTOP column and level, the first x and y and the
 * median qc and fs. The levels split GeoTOP's voxels, so that the samples lie on the cells' levels.
 */
export function samplesOf(readings: Reading[], h: number): Sample[] {
  const groups = new Map<string, { sample: Sample; qc: Array<number | null>; fs: Array<number | null> }>();
  const levels = Math.round(VOXEL / h);
  for (const reading of readings) {
    const columnX = Math.floor(reading.x / COLUMN) * COLUMN;
    const columnY = Math.floor(reading.y / COLUMN) * COLUMN;
    const voxelZ = roundHalfEven(reading.z * 2) / 2;
    const level = Math.min(Math.max(Math.floor((reading.z - voxelZ + VOXEL / 2) / h), 0), levels - 1);
    const z = round3(voxelZ - VOXEL / 2 + (level + 0.5) * h);
    const key = `${reading.bro_id} ${columnX} ${columnY} ${z}`;
    let group = groups.get(key);
    if (!group) {
      group = {
        sample: { bro_id: reading.bro_id, x: reading.x, y: reading.y, z, column_x: columnX, column_y: columnY, qc: null, fs: null },
        qc: [],
        fs: [],
      };
      groups.set(key, group);
    }
    group.qc.push(reading.qc);
    group.fs.push(reading.fs);
  }
  return [...groups.values()].map(({ sample, qc, fs }) => ({ ...sample, qc: median(qc), fs: median(fs) }));
}

/**
 * The samples on the grid's simulated levels, classified: the ground of a GeoTOP column is the top of
 * its highest cell with a stratigraphic unit.
 *
 * The grid stops at the highest simulated level, where GeoTOP itself goes on, so that the ground can lie
 * lower than the notebook's: in column x 121,900, y 488,500 it is 1.25 m instead of 1.75 m, and 33 of
 * the samples there get another zone than their layer in cpts_interpreted_25cm.parquet. That is accepted.
 */
export function classifySamples(
  samples: Sample[],
  grid: Grid,
  h: number,
  gammaMissing: number,
): { samples: Sample[]; usable: ClassifiedSample[] } {
  // Per GeoTOP column and level of cells with a stratigraphic unit: whether any of them is simulated
  const simulated = new Map<string, boolean>();
  const ground = new Map<string, number>();
  const levels = new Set<number>();
  const [nx, ny] = [grid.x.length, grid.y.length];
  grid.z.forEach((cz, k) => {
    const z = round3(cz);
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const index = (k * ny + j) * nx + i;
        if (grid.stratigraphicUnit[index] < 0) {
          continue;
        }
        const column = `${Math.floor(grid.x[i] / COLUMN) * COLUMN} ${Math.floor(grid.y[j] / COLUMN) * COLUMN}`;
        const key = `${column} ${z}`;
        simulated.set(key, (simulated.get(key) ?? false) || grid.domain[index] >= 0);
        ground.set(column, Math.max(ground.get(column) ?? -Infinity, z + h / 2));
        levels.add(z);
      }
    }
  });
  const kept = samples.filter((s) => simulated.get(`${s.column_x} ${s.column_y} ${s.z}`));
  const usable = kept.filter((s) => s.qc !== null && s.qc > 0 && s.fs !== null && s.fs > 0);

  // qc and fs per CPT (by bro_id) and level, from the top down
  const zs = [...levels].sort((a, b) => b - a);
  const depthOf = new Map(zs.map((z, k) => [z, k]));
  const ids = [...new Set(usable.map((s) => s.bro_id))].sort();
  const rowOf = new Map(ids.map((id, row) => [id, row]));
  const qc = new Float64Array(ids.length * zs.length).fill(NaN);
  const fs = new Float64Array(ids.length * zs.length).fill(NaN);
  const grounds = new Float64Array(ids.length);
  const cells = usable.map((s) => {
    const row = rowOf.get(s.bro_id)!;
    const cell = row * zs.length + depthOf.get(s.z)!;
    qc[cell] = s.qc!;
    fs[cell] = s.fs!;
    grounds[row] = ground.get(`${s.column_x} ${s.column_y}`)!;
    return cell;
  });
  const result = robertson(qc, fs, zs, grounds, gammaMissing);
  return {
    samples: kept,
    usable: usable.map((s, k) => ({ ...s, zone: result.zone[cells[k]], ic: result.ic[cells[k]] })),
  };
}
