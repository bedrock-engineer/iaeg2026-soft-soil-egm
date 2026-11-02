// Checks what the page computes from R2 against the notebooks' numbers, in Node with nothing but the
// page's own modules: npm run check. Needs the internet (R2); behind a proxy, Node 22 needs
// NODE_USE_ENV_PROXY=1.
import { strict as assert } from "node:assert";
import { asyncBufferFromUrl, parquetReadObjects } from "hyparquet";
import { compressors } from "hyparquet-compressors";
import { classifySamples, readReadings, samplesOf } from "../src/cpt-samples.ts";
import { crossSectionTraits } from "../src/cross-section-traits.ts";
import { buildingFootprint, modelParquetUrl } from "../src/project-geometry.ts";
import { between, siteCrs } from "../src/site-crs.ts";
import { gammaMissing, SOIL_MODEL_URL, SoilModel } from "../src/soil-model.ts";

const SAMPLE_HEIGHT = 0.25;

async function read(url: string, columns: string[]) {
  const file = await asyncBufferFromUrl({ url });
  return (await parquetReadObjects({ file, columns, compressors })) as Record<string, any>[];
}

function bbox(points: number[][]) {
  return [0, 1, 2].map((axis) =>
    points.reduce(([min, max], p) => [Math.min(min, p[axis]), Math.max(max, p[axis])], [Infinity, -Infinity]),
  );
}

function check(name: string, actual: unknown, expected: unknown) {
  assert.deepEqual(actual, expected, name);
  console.log(`ok  ${name}: ${JSON.stringify(actual)}`);
}

const close = (value: number, expected: number, tolerance: number) => Math.abs(value - expected) <= tolerance;

const soil = new SoilModel();
const [grid, readings, gamma, building, layers, volumes] = await Promise.all([
  soil.grid(),
  readReadings(),
  gammaMissing(),
  read(modelParquetUrl, ["mesh", "geog", "bim_crs"]),
  read(`${SOIL_MODEL_URL}cpts_interpreted_25cm.parquet`, ["properties", "bim_crs"]),
  read(`${SOIL_MODEL_URL}sbtn_volumes_25cm.parquet`, ["mesh", "bim_crs"]),
]);

// The CRSs: the building in the soil's CRS, and the volumes, as the notebook has them
const buildingCrs = siteCrs(building.find((r) => r.bim_crs).bim_crs);
const soilCrs = siteCrs(volumes[0].bim_crs);
const toSoil = between(buildingCrs, soilCrs);
const vertices = (rows: Record<string, any>[]) =>
  rows.flatMap((r) => {
    const v: number[] = r.mesh?.vertices ?? [];
    return Array.from({ length: v.length / 3 }, (_, i) => [v[3 * i], v[3 * i + 1], v[3 * i + 2]]);
  });
const [bx, by, bz] = bbox(vertices(building).map(toSoil));
console.log("    building in the GeoTOP CRS", { x: bx, y: by, z: bz });
assert(close(bx[0], -66, 0.1) && close(bx[1], 18.6, 0.1), "building x");
assert(close(by[0], -33, 0.1) && close(by[1], 32, 0.1), "building y");
assert(close(bz[0], -3.9, 0.05) && close(bz[1], 15.9, 0.05), "building z");
const [vx, vy, vz] = bbox(vertices(volumes));
console.log("    volumes in the GeoTOP CRS", { x: vx, y: vy, z: vz });
assert(close(vx[0], -300, 0.01) && close(vx[1], 300, 0.01) && close(vy[0], -250, 0.01) && close(vy[1], 250, 0.01));
assert(close(vz[0], -36.25, 0.01) && close(vz[1], 1.25, 0.01));
// And the round trip into the building's CRS, as the viewer gets them
const back = between(soilCrs, buildingCrs);
const [x0, y0, z0] = [12.3, -45.6, -7.8];
const there = toSoil(back([x0, y0, z0]));
assert(close(there[0], x0, 1e-6) && close(there[1], y0, 1e-6) && close(there[2], z0, 1e-6), "round trip");
console.log("ok  the building and the volumes line up, as bpl.to_crs puts them");

// The samples
const all = samplesOf(readings, SAMPLE_HEIGHT);
const { samples, usable } = classifySamples(all, grid, SAMPLE_HEIGHT, gamma);
check("gamma_missing", gamma, 18);
check("samples", samples.length, 8961);
check("usable samples", usable.length, 8901);

// Against the layers of the interpreted CPTs: only the 33 in the column where the grid gives a lower
// ground may differ
const byCpt = new Map<string, Array<Record<string, any>>>();
for (const { properties } of layers) {
  const layer = properties.CPT;
  byCpt.set(layer.bro_id, [...(byCpt.get(layer.bro_id) ?? []), layer]);
}
const differing = usable.filter((s) => {
  const layer = byCpt.get(s.bro_id)?.find((l) => l.bottom_z < s.z && s.z < l.top_z);
  assert(layer, `no layer for ${s.bro_id} at ${s.z}`);
  return Number(layer.sbtn_zone) !== s.zone;
});
check("samples whose zone differs from their layer", differing.length, 33);
check(
  "the columns they are in",
  [...new Set(differing.map((s) => `${s.column_x} ${s.column_y}`))],
  ["121900 488500"],
);

// The cross sections' traits
const { outline, ring } = buildingFootprint(building.filter((r) => r.geog).map((r) => r.geog));
const xs = ring.map((p) => p[0]);
const ys = ring.map((p) => p[1]);
console.log("    footprint", { area_m2: outline.properties!.area_m2, x: [Math.min(...xs), Math.max(...xs)], y: [Math.min(...ys), Math.max(...ys)] });
assert(close(outline.properties!.area_m2, 1930, 15), "footprint area");
assert(close(Math.min(...xs), 122034, 1) && close(Math.max(...xs), 122119, 1), "footprint x");
assert(close(Math.min(...ys), 488717, 1) && close(Math.max(...ys), 488782, 1), "footprint y");
const { traits } = crossSectionTraits(grid, all, ring, {});
check("cells of the kept zones", traits.voxels.length, 392743);
check("lithologies", traits.lithologies.map((l) => l.name), [
  "2 Organic soil",
  "3 Clay",
  "4 Silt mixture",
  "5 Sand mixture",
  "6 Sand",
  "7 Dense sand to gravelly sand",
]);
check("start", [traits.x, traits.y, traits.z, traits.selected_cpt], [122080, 488750, -14.125, "CPT000000198164"]);
check("zones of the usable samples", [...new Set(usable.map((s) => s.zone))].sort(), [1, 2, 3, 4, 5, 6, 7, 8]);
console.log("All checks passed.");
