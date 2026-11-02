// The soil model on R2, as notebooks/sync_r2.py publishes it: the cells of the 25 cm run in a Zarr
// group, the CPTs' readings and the run's definition. Nothing is checked in; the page reads them by name,
// since the bucket cannot be listed.
import { decompress } from "fzstd";
import * as zarr from "zarrita";
import { SOIL_BEHAVIOR_COLORS, SOIL_BEHAVIOR_TYPES } from "./robertson.ts";

export const SOIL_MODEL_URL = "https://r2.eu.bedrock.engineer/nl-amsterdam-noord/";

/**
 * The SBTn zones the page shows. Zones 1, 8 and 9 hardly occur, and are left out of the volumes,
 * the CPT layers, the cells, the legends and the CPT samples. Their numbers are Robertson's.
 */
export const KEPT_ZONES = [2, 3, 4, 5, 6, 7];

export const isKept = (zone: number) => KEPT_ZONES.includes(zone);

/** A zone with its number, as the notebooks label it: "3 Clay" */
export const zoneLabel = (zone: number) => `${zone} ${SOIL_BEHAVIOR_TYPES[zone]}`;

export const zoneColor = (zone: number) => SOIL_BEHAVIOR_COLORS[zone];

// fzstd instead of numcodecs' WebAssembly zstd, which zarrita would load: hyparquet-compressors already
// brings it for the Parquet files
zarr.registry.set("zstd", () => ({
  fromConfig: () => ({
    kind: "bytes_to_bytes" as const,
    encode(): never {
      throw new Error("The page only reads the soil model");
    },
    decode: (bytes: Uint8Array) => decompress(bytes),
  }),
}) as never);

/** The cells' grid: their centers in RD New and m NAP, and what the page always needs of them */
export interface Grid {
  /** Cell centers, x and y ascending, z ascending */
  x: Float64Array;
  y: Float64Array;
  z: Float64Array;
  /** The cells' size in m */
  cell: { x: number; y: number; z: number };
  /** Flat in (z, y, x) order, as the arrays are */
  sbtnMostLikely: Int8Array;
  /** -1 where there is none */
  domain: Int8Array;
  stratigraphicUnit: Int8Array;
  /** Their names, from flag_meanings */
  domains: string[];
  units: string[];
}

/** The flat index of a cell */
export const cellIndex = (grid: Grid, k: number, j: number, i: number) =>
  (k * grid.y.length + j) * grid.x.length + i;

/** The 3D float arrays of the cells, (z, y, x) */
export type CellValues = "qc_p50" | "ic_p10" | "ic_p50" | "ic_p90";

export class SoilModel {
  readonly #group = zarr.open.v3(
    zarr.root(new zarr.FetchStore(`${SOIL_MODEL_URL}soil_model.zarr`)).resolve("25cm"),
    { kind: "group" },
  );
  readonly #values = new Map<string, Promise<Float32Array>>();
  #probability: Promise<Float32Array[]> | null = null;

  async #read<T>(name: string): Promise<{ data: T; attrs: Record<string, unknown> }> {
    const array = await zarr.open.v3((await this.#group).resolve(name), { kind: "array" });
    const { data } = await zarr.get(array);
    return { data: data as T, attrs: array.attrs as Record<string, unknown> };
  }

  /** The grid: a few hundred kB of int8, the first thing the sections need */
  async grid(): Promise<Grid> {
    const [x, y, z, sbtnMostLikely, domain, unit] = await Promise.all([
      this.#read<Float64Array>("x"),
      this.#read<Float64Array>("y"),
      this.#read<Float64Array>("z"),
      this.#read<Int8Array>("sbtn_most_likely"),
      this.#read<Int8Array>("domain"),
      this.#read<Int8Array>("stratigraphic_unit"),
    ]);
    const names = (attrs: Record<string, unknown>) => String(attrs.flag_meanings).split(" ");
    return {
      x: x.data,
      y: y.data,
      z: z.data,
      cell: { x: x.data[1] - x.data[0], y: y.data[1] - y.data[0], z: z.data[1] - z.data[0] },
      sbtnMostLikely: sbtnMostLikely.data,
      domain: domain.data,
      stratigraphicUnit: unit.data,
      domains: names(domain.attrs),
      units: names(unit.attrs),
    };
  }

  /** One of the float arrays, read once: some 2 MB decoded */
  values(name: CellValues): Promise<Float32Array> {
    if (!this.#values.has(name)) {
      this.#values.set(name, this.#read<Float32Array>(name).then(({ data }) => data));
    }
    return this.#values.get(name)!;
  }

  /** The probability of each zone per cell, by zone number (0 is empty): 16 MB decoded, read once */
  probability(): Promise<Float32Array[]> {
    this.#probability ??= (async () => {
      const [{ data: zones }, array] = await Promise.all([
        this.#read<BigInt64Array>("sbtn_zone"),
        zarr.open.v3((await this.#group).resolve("sbtn_probability"), { kind: "array" }),
      ]);
      const byZone: Float32Array[] = [];
      // One zone at a time: its chunks are its own
      await Promise.all(
        [...zones].map(async (zone, k) => {
          const { data } = await zarr.get(array, [k, null, null, null]);
          byZone[Number(zone)] = data as Float32Array;
        }),
      );
      return byZone;
    })();
    return this.#probability;
  }
}

/** The run's definition, of which the classification's gamma_missing (kN/m³) */
export async function gammaMissing(): Promise<number> {
  const response = await fetch(`${SOIL_MODEL_URL}soil_model_25cm.json`);
  if (!response.ok) {
    throw new Error(`soil_model_25cm.json: HTTP ${response.status}`);
  }
  return (await response.json()).classification.gamma_missing;
}
