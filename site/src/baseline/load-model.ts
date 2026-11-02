// Browser adapter for the unchanged upstream bimpolars page and GeoSpeckleViewer.
import {
  asyncBufferFromUrl,
  parquetMetadataAsync,
  parquetReadObjects,
} from "hyparquet";
import { compressors } from "hyparquet-compressors";
import { Matrix4, Vector3 } from "three";
import type {
  GroundMap,
  SpeckleObject,
  Tileset,
} from "../../vendor/geospeckle-viewer/lib/types";
import { buildingFootprint, modelParquetUrl } from "../project-geometry.ts";
import { between, siteCrs } from "../site-crs.ts";
import { isKept, SOIL_MODEL_URL } from "../soil-model.ts";
import type { Footprints } from "./footprints";

type Geometry = GeoJSON.Polygon | GeoJSON.MultiPolygon;
type Row = {
  id: string;
  name: string;
  class: string;
  container: string | null;
  elevation: number | null;
  mesh: {
    vertices: number[];
    faces: number[];
    styles: Array<{ name: string; rgba: number[]; face_count: number }>;
  } | null;
  geog: Geometry | null;
  footprint: Geometry | null;
  model_name?: string;
  /** The soil's property set: {"CPT": {...}} or {"SBTn volume": {...}} */
  properties?: Record<string, Record<string, unknown>> | null;
  bim_crs?: string | null;
};

/** The soil's BimDataFrames beside the building, and their property sets' names */
const SOIL = {
  cpts: { url: `${SOIL_MODEL_URL}cpts_interpreted_25cm.parquet`, propertySet: "CPT" },
  volumes: { url: `${SOIL_MODEL_URL}sbtn_volumes_25cm.parquet`, propertySet: "SBTn volume" },
};

/** Parquet's int64 arrives as BigInt, which JSON has no place for: plain numbers */
function plain(value: unknown): unknown {
  if (typeof value === "bigint") return Number(value);
  if (Array.isArray(value)) return value.map(plain);
  if (value && typeof value === "object" && !ArrayBuffer.isView(value))
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, plain(v)]));
  return value;
}
const positions = (g: Geometry): number[][] =>
  g.type === "Polygon" ? g.coordinates.flat() : g.coordinates.flat(2);
const ecef = (p: number[]) => {
  const lon = (p[0] * Math.PI) / 180,
    lat = (p[1] * Math.PI) / 180,
    h = p[2] ?? 0;
  const n = 6378137 / Math.sqrt(1 - 0.00669437999014 * Math.sin(lat) ** 2);
  return [
    (n + h) * Math.cos(lat) * Math.cos(lon),
    (n + h) * Math.cos(lat) * Math.sin(lon),
    (n * (1 - 0.00669437999014) + h) * Math.sin(lat),
  ];
};
function solve(matrix: number[][], values: number[]): number[] {
  const a = matrix.map((r, i) => [...r, values[i]]);
  for (let i = 0; i < 4; i++) {
    let pivot = i;
    for (let j = i + 1; j < 4; j++)
      if (Math.abs(a[j][i]) > Math.abs(a[pivot][i])) pivot = j;
    [a[i], a[pivot]] = [a[pivot], a[i]];
    if (Math.abs(a[i][i]) < 1e-12)
      throw new Error(
        "The Parquet footprint coordinates do not span a 3D site CRS.",
      );
    const d = a[i][i];
    for (let k = i; k < 5; k++) a[i][k] /= d;
    for (let j = 0; j < 4; j++)
      if (j !== i) {
        const f = a[j][i];
        for (let k = i; k < 5; k++) a[j][k] -= f * a[i][k];
      }
  }
  return a.map((r) => r[4]);
}
/** Paired footprint/geog vertices encode the exact site's linearized ECEF transform,
 * including its ellipsoidal height. Recover it rather than guessing a Dutch geoid offset.
 */
function siteTransform(rows: Row[], unit: number): Matrix4 {
  const pairs: Array<[number[], number[]]> = [];
  for (const r of rows) {
    if (!r.geog || !r.footprint) continue;
    const g = positions(r.geog),
      p = positions(r.footprint);
    if (g.length !== p.length) continue;
    for (let i = 0; i < g.length; i += Math.max(1, Math.floor(g.length / 3)))
      if (g[i].length === 3 && p[i].length === 3)
        pairs.push([ecef(g[i]), p[i].map((v) => v * unit)]);
  }
  if (pairs.length < 4)
    throw new Error("The model has no paired 3D footprint/geog coordinates.");
  const origin = pairs[0][0],
    normal = Array.from({ length: 4 }, () => [0, 0, 0, 0]),
    rhs = Array.from({ length: 3 }, () => [0, 0, 0, 0]);
  for (const [e, p] of pairs) {
    const v = [e[0] - origin[0], e[1] - origin[1], e[2] - origin[2], 1];
    for (let i = 0; i < 4; i++) {
      for (let j = 0; j < 4; j++) normal[i][j] += v[i] * v[j];
      for (let k = 0; k < 3; k++) rhs[k][i] += v[i] * p[k];
    }
  }
  const r = rhs.map((v) => solve(normal, v));
  for (const row of r)
    row[3] -= row[0] * origin[0] + row[1] * origin[1] + row[2] * origin[2];
  const m = new Matrix4().set(
    ...([...r.flat(), 0, 0, 0, 1] as [
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
      number,
    ]),
  );
  const residual = Math.max(
    ...pairs
      .slice(0, 100)
      .map(([e, p]) =>
        new Vector3(...(e as [number, number, number]))
          .applyMatrix4(m)
          .distanceTo(new Vector3(...(p as [number, number, number]))),
      ),
  );
  if (residual > 0.05)
    throw new Error(
      `Site CRS recovery residual ${residual.toFixed(3)} m exceeds 5 cm.`,
    );
  return m;
}
function geographic(p: Vector3): number[] {
  const lon = Math.atan2(p.y, p.x),
    rho = Math.hypot(p.x, p.y);
  let lat = Math.atan2(p.z, rho * (1 - 0.00669437999014)),
    h = 0;
  for (let i = 0; i < 8; i++) {
    const n = 6378137 / Math.sqrt(1 - 0.00669437999014 * Math.sin(lat) ** 2);
    h = rho / Math.cos(lat) - n;
    lat = Math.atan2(p.z, rho * (1 - (0.00669437999014 * n) / (n + h)));
  }
  return [(lon * 180) / Math.PI, (lat * 180) / Math.PI, h];
}
function groundMap(rows: Row[], transform: Matrix4): GroundMap {
  const geo = rows.filter((r) => r.geog).flatMap((r) => positions(r.geog!));
  const lon = geo.map((p) => p[0]),
    lat = geo.map((p) => p[1]);
  const center = (Math.min(...lat) + Math.max(...lat)) / 2;
  const bounds: [number, number, number, number] = [
    Math.min(...lon) - 150 / (111320 * Math.cos((center * Math.PI) / 180)),
    Math.min(...lat) - 150 / 111320,
    Math.max(...lon) + 150 / (111320 * Math.cos((center * Math.PI) / 180)),
    Math.max(...lat) + 150 / 111320,
  ];
  const origin = geographic(
    new Vector3(0, 0, 0).applyMatrix4(transform.clone().invert()),
  );
  const world = (x: number, y: number) =>
    new Vector3(
      ...(ecef([x, y, origin[2]]) as [number, number, number]),
    ).applyMatrix4(transform);
  const x = (bounds[0] + bounds[2]) / 2,
    y = (bounds[1] + bounds[3]) / 2,
    o = world(x, y),
    dx = world(x + 1e-5, y)
      .sub(o)
      .multiplyScalar(1e5),
    dy = world(x, y + 1e-5)
      .sub(o)
      .multiplyScalar(1e5);
  const merc = (v: number) => Math.asinh(Math.tan((v * Math.PI) / 180));
  return {
    bounds,
    width: 2048,
    height: Math.round(
      (2048 * (merc(bounds[3]) - merc(bounds[1]))) /
        (((bounds[2] - bounds[0]) * Math.PI) / 180),
    ),
    lnglat_to_world: [
      dx.x,
      dy.x,
      o.x - dx.x * x - dy.x * y,
      dx.y,
      dy.y,
      o.y - dx.y * x - dy.y * y,
    ],
    z: 0,
    opacity: 0.85,
  };
}
/** One model of the viewer: a root and its elements, each with its meshes. The prefix keeps the ids of
 * several models apart; elementIds holds each row's element id, where it has one. */
function modelObjects(
  rows: Row[],
  units: string,
  prefix: string,
  rootId: string,
  rootName: string,
): { objects: SpeckleObject[]; elementIds: Array<string | undefined> } {
  const elementIds: Array<string | undefined> = [];
  const objects: SpeckleObject[] = [],
    elements: Array<{ referencedId: string; speckle_type: string }> = [],
    materials = new Map<string, { value: SpeckleObject; objects: string[] }>();
  const ref = (id: string) => ({ referencedId: id, speckle_type: "reference" });
  for (const [ri, row] of rows.entries()) {
    if (!row.mesh || row.class === "IfcOpeningElement") continue;
    const mesh = row.mesh,
      display: unknown[] = [];
    let offset = 0;
    const styles = mesh.styles?.length
      ? mesh.styles
      : [
          {
            name: "Default",
            rgba: [0.7, 0.7, 0.7, 1],
            face_count: mesh.faces.length / 3,
          },
        ];
    for (const [si, style] of styles.entries()) {
      const id = `${prefix}mesh-${ri}-${si}`,
        appId = `${row.id}/${si}`,
        faces: number[] = [];
      for (let i = offset * 3; i < (offset + style.face_count) * 3; i += 3)
        faces.push(3, mesh.faces[i], mesh.faces[i + 1], mesh.faces[i + 2]);
      offset += style.face_count;
      if (!faces.length) continue;
      objects.push({
        id,
        speckle_type: "Objects.Geometry.Mesh",
        applicationId: appId,
        units,
        vertices: mesh.vertices,
        faces,
        colors: [],
        textureCoordinates: [],
        vertexNormals: [],
        totalChildrenCount: 0,
      });
      display.push(ref(id));
      const key = JSON.stringify([style.name, style.rgba]);
      let material = materials.get(key);
      if (!material) {
        const [r, g, b, a] = style.rgba;
        material = {
          value: {
            id: `${prefix}material-${materials.size}`,
            speckle_type: "Objects.Other.RenderMaterial",
            name: style.name ?? "Default",
            diffuse:
              (255 << 24) |
              (Math.round(r * 255) << 16) |
              (Math.round(g * 255) << 8) |
              Math.round(b * 255),
            opacity: a ?? 1,
            metalness: 0,
            roughness: 1,
          },
          objects: [],
        };
        materials.set(key, material);
      }
      material.objects.push(appId);
    }
    const element: SpeckleObject = {
      id: `${prefix}element-${ri}`,
      speckle_type: "Objects.Data.DataObject",
      applicationId: row.id,
      name: row.name ?? row.id,
      category: row.class,
      container: row.container,
      properties: row.properties ?? { model_name: row.model_name },
      displayValue: display,
      totalChildrenCount: display.length,
    };
    objects.push(element);
    elements.push(ref(element.id));
    elementIds[ri] = element.id;
  }
  const root: SpeckleObject = {
    id: rootId,
    speckle_type: "Speckle.Core.Models.Collections.Collection",
    name: rootName,
    units,
    elements,
    totalChildrenCount: objects.length,
    renderMaterialProxies: [...materials.values()].map((m, i) => ({
      id: `${prefix}proxy-${i}`,
      speckle_type: "Objects.Other.RenderMaterialProxy",
      value: m.value,
      objects: m.objects,
      totalChildrenCount: 0,
    })),
    __closure: Object.fromEntries(
      objects.map((o) => [
        o.id,
        o.speckle_type === "Objects.Geometry.Mesh" ? 2 : 1,
      ]),
    ),
  };
  return { objects: [root, ...objects], elementIds };
}
async function contextTiles(
  bounds: number[],
  transform: Matrix4,
  outline: GeoJSON.Feature<GeoJSON.Polygon>,
): Promise<Tileset> {
  const radians = bounds.map((v) => (v * Math.PI) / 180),
    leaves: Record<string, unknown>[] = [],
    url =
      "https://api.pdok.nl/kadaster/3d-basisvoorziening/ogc/v1/collections/gebouwen/3dtiles?f=json";
  const overlaps = (t: any) => {
    const r = t.boundingVolume?.region;
    return (
      !r ||
      (r[0] <= radians[2] &&
        r[2] >= radians[0] &&
        r[1] <= radians[3] &&
        r[3] >= radians[1])
    );
  };
  async function walk(
    t: any,
    base: string,
    m: Matrix4,
    refine: string,
  ): Promise<void> {
    if (!overlaps(t)) return;
    refine = t.refine ?? refine;
    const current = t.transform
      ? m.clone().multiply(new Matrix4().fromArray(t.transform))
      : m;
    const uri = t.content?.uri ?? t.content?.url;
    if (uri && uri.split("?")[0].endsWith(".json")) {
      const next = new URL(uri, base).href;
      const response = await fetch(next);
      if (!response.ok) throw new Error(`3D BAG HTTP ${response.status}`);
      await walk((await response.json()).root, next, current, refine);
      return;
    }
    const children = (t.children ?? []).filter(overlaps),
      finest = !children.length || t.geometricError === 0;
    if (uri && (finest || refine === "ADD"))
      leaves.push({
        boundingVolume: t.boundingVolume,
        geometricError: 0,
        transform: current.toArray(),
        content: { uri: new URL(uri, base).href },
      });
    if (!finest)
      await Promise.all(
        children.map((c: any) => walk(c, base, current, refine)),
      );
  }
  const response = await fetch(url);
  if (!response.ok) throw new Error(`3D BAG HTTP ${response.status}`);
  await walk((await response.json()).root, url, new Matrix4(), "REPLACE");
  if (!leaves.length) throw new Error("No 3D BAG tiles cover Amsterdam Noord.");
  const originHeight = geographic(
    new Vector3().applyMatrix4(transform.clone().invert()),
  )[2];
  const rings = outline.geometry.coordinates.map((ring) =>
    ring.map((p) => {
      const w = new Vector3(
        ...(ecef([p[0], p[1], originHeight]) as [number, number, number]),
      ).applyMatrix4(transform);
      return [w.x, w.y] as [number, number];
    }),
  );
  return {
    tileset: {
      asset: { version: "1.1" },
      geometricError: 1000,
      root: {
        boundingVolume: { region: [...radians, -1000, 10000] },
        geometricError: 1000,
        refine: "ADD",
        children: leaves,
      },
    },
    ecef_to_world: transform.toArray(),
    attribution: "3D Basisvoorziening © Kadaster (CC BY 4.0)",
    hide_within: [rings],
  };
}
async function readRows(url: string, columns: string[]): Promise<Row[]> {
  const file = await asyncBufferFromUrl({ url });
  const metadata = await parquetMetadataAsync(file);
  return (await parquetReadObjects({
    file,
    metadata,
    columns,
    compressors,
    utf8: false,
  })) as Row[];
}

/**
 * The interpreted CPTs and the SBTn volumes of the kept zones, with their vertices in the building's
 * CRS, whatever site grid on RD New + NAP that is: the soil's is in meters around RD 122,100 488,750.
 */
async function readSoil(building: Promise<Row[]>) {
  const read = async ({ url, propertySet }: (typeof SOIL)[keyof typeof SOIL]) => {
    const rows = await readRows(url, ["id", "name", "class", "properties", "mesh", "geog", "bim_crs"]);
    const buildingCrs = siteCrs((await building).find((r) => r.bim_crs)!.bim_crs!);
    const toBuilding = between(siteCrs(rows[0].bim_crs!), buildingCrs);
    return rows
      .map((row) => ({ ...row, properties: plain(row.properties) as Row["properties"] }))
      .filter((row) => isKept(Number(row.properties![propertySet].sbtn_zone)))
      .map((row) => {
        const vertices = row.mesh!.vertices;
        const moved: number[] = new Array(vertices.length);
        for (let i = 0; i < vertices.length; i += 3) {
          const p = toBuilding([vertices[i], vertices[i + 1], vertices[i + 2]]);
          moved[i] = p[0];
          moved[i + 1] = p[1];
          moved[i + 2] = p[2];
        }
        return { ...row, container: null, elevation: null, footprint: null, mesh: { ...row.mesh!, vertices: moved } };
      });
  };
  const [cpts, volumes] = await Promise.all([read(SOIL.cpts), read(SOIL.volumes)]);
  return { cpts, volumes };
}

export async function loadR2Model() {
  const reading = readRows(modelParquetUrl, [
    "id",
    "name",
    "class",
    "container",
    "elevation",
    "geog",
    "footprint",
    "mesh",
    "model_name",
    "bim_crs",
  ]);
  const [rows, { cpts, volumes }] = await Promise.all([reading, readSoil(reading)]);
  // The viewer's world is the building's CRS in meters
  const buildingCrs = siteCrs(rows.find((r) => r.bim_crs)!.bim_crs!);
  const units = { 1: "m", 0.001: "mm" }[buildingCrs.unit];
  if (!units) {
    throw new Error(`${buildingCrs.name} is neither in meters nor in millimeters`);
  }
  const { outline: outlineFeature, ring } = buildingFootprint(
    rows.filter((r) => r.geog).map((r) => r.geog!),
  );
  const storeys = new Map(
    rows
      .filter((r) => r.class === "Levels" || r.class === "IfcBuildingStorey")
      .map((r) => [r.id, r]),
  );
  const footprints: Footprints = {
    type: "FeatureCollection",
    features: [...rows, ...cpts, ...volumes]
      .filter((r) => r.mesh && r.geog && r.class !== "IfcOpeningElement")
      .map((r) => ({
        type: "Feature",
        properties: {
          id: r.id,
          class: r.class,
          name: r.name,
          storey: storeys.get(r.container ?? "")?.name ?? null,
          elevation:
            storeys.get(r.container ?? "")?.elevation == null
              ? null
              : storeys.get(r.container ?? "")!.elevation! * buildingCrs.unit,
        },
        geometry: {
          ...r.geog!,
          coordinates:
            r.geog!.type === "Polygon"
              ? r.geog!.coordinates.map((ring) =>
                  ring.map((p) => p.slice(0, 2)),
                )
              : r.geog!.coordinates.map((polygon) =>
                  polygon.map((ring) => ring.map((p) => p.slice(0, 2))),
                ),
        } as Geometry,
      })),
  };
  // The ground map and the 3D BAG cover the volumes, which reach well beyond the building
  const transform = siteTransform(rows, buildingCrs.unit),
    ground_map = groundMap([...rows, ...volumes], transform);
  const building = modelObjects(
    rows,
    units,
    "",
    "amsterdam-noord-rvt",
    "Amsterdam Noord · Revit architecture + structure",
  );
  const cptModel = modelObjects(cpts, units, "cpt-", "amsterdam-noord-cpts", "Interpreted CPTs");
  const volumeModel = modelObjects(volumes, units, "volume-", "amsterdam-noord-sbtn-volumes", "SBTn volumes");
  // The elements of each checkbox, by their viewer ids: the viewer hides them without reloading
  const groups = {
    architecture: rows.flatMap((r, i) =>
      r.model_name?.endsWith("-arch") && building.elementIds[i] ? [building.elementIds[i]!] : [],
    ),
    structure: rows.flatMap((r, i) =>
      r.model_name?.endsWith("-str") && building.elementIds[i] ? [building.elementIds[i]!] : [],
    ),
    cpts: cptModel.elementIds.filter((id) => id !== undefined),
    volumes: new Map(
      volumes.map((r, i) => [
        Number(r.properties![SOIL.volumes.propertySet].sbtn_zone),
        [volumeModel.elementIds[i]!],
      ]),
    ),
  };
  const packed = await new Response(
    new Blob([JSON.stringify([building.objects, cptModel.objects, volumeModel.objects])])
      .stream()
      .pipeThrough(new CompressionStream("gzip")),
  ).arrayBuffer();
  // Return the model immediately; surrounding tiles load alongside it.
  const tiles = contextTiles(ground_map.bounds, transform, outlineFeature);
  return {
    state: { ground_map, tilesets: [], markers: [], height: null },
    objects: packed,
    groups,
    footprints,
    outline: {
      type: "FeatureCollection",
      features: [outlineFeature],
    } as GeoJSON.FeatureCollection,
    /** The building's outline as a ring in RD New, for the cross sections */
    ring,
    tiles,
    rowCount: rows.length,
  };
}
