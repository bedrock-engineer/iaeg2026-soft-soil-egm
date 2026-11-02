// The georeferenced BIM CRSs of the BimDataFrames, from their bim_crs column: a site grid derived from
// RD New by an affine transformation, and a site z derived from NAP by an offset, such as the soil's
// "GeoTOP georeferenced BIM CRS" in meters around 122,100 488,750, or one in millimeters and turned.
// This is the browser's bpl.to_crs(frame, building.crs): both through RD New + NAP, exactly.

type Unit = string | { conversion_factor: number };
interface Parameter {
  name: string;
  value: number;
  unit: Unit;
}
interface Derived {
  type: string;
  name: string;
  base_crs: { id?: { code: number } };
  conversion: { method: { name: string }; parameters: Parameter[] };
  coordinate_system: { axis: Array<{ unit: Unit }> };
}

/** A unit in meters: "metre" and "unity" are 1 */
const meters = (unit: Unit) => (typeof unit === "string" ? 1 : unit.conversion_factor);

export interface SiteCrs {
  name: string;
  /** Meters per unit of its x, y and z: the building's CRS has been in millimeters */
  unit: number;
  /** Site coordinates, in the CRS's units, to RD New and m NAP */
  toRd(point: number[]): [number, number, number];
  /** RD New and m NAP to site coordinates */
  fromRd(point: number[]): [number, number, number];
}

/** A georeferenced BIM CRS from its PROJJSON; anything but RD New + NAP under it is refused */
export function siteCrs(projjson: string | Record<string, unknown>): SiteCrs {
  const crs = typeof projjson === "string" ? JSON.parse(projjson) : projjson;
  const [horizontal, vertical] = (crs.components ?? []) as Derived[];
  if (
    horizontal?.base_crs.id?.code !== 28992 ||
    horizontal.conversion.method.name !== "Affine parametric transformation" ||
    vertical?.base_crs.id?.code !== 5709 ||
    vertical.conversion.method.name !== "Vertical Offset"
  ) {
    throw new Error(`${crs.name} is not a site grid on RD New + NAP`);
  }
  // In the site's own units: A0 and B0 in theirs, A1 to B2 from RD meters to the site's units
  const [xUnit, yUnit] = horizontal.coordinate_system.axis.map((axis) => meters(axis.unit));
  const zUnit = meters(vertical.coordinate_system.axis[0].unit);
  if (xUnit !== yUnit || xUnit !== zUnit) {
    throw new Error(`${crs.name} has different units along its axes`);
  }
  const p = Object.fromEntries(
    horizontal.conversion.parameters.map(({ name, value, unit }) => [
      name,
      name === "A0" ? (value * meters(unit)) / xUnit : name === "B0" ? (value * meters(unit)) / yUnit : value,
    ]),
  );
  const [offset] = vertical.conversion.parameters.map(({ value, unit }) => value * meters(unit));
  const determinant = p.A1 * p.B2 - p.A2 * p.B1;
  return {
    name: crs.name,
    unit: xUnit,
    toRd([x, y, z = 0]) {
      const [dx, dy] = [x - p.A0, y - p.B0];
      return [(p.B2 * dx - p.A2 * dy) / determinant, (p.A1 * dy - p.B1 * dx) / determinant, z * zUnit - offset];
    },
    fromRd([x, y, z = 0]) {
      return [p.A0 + p.A1 * x + p.A2 * y, p.B0 + p.B1 * x + p.B2 * y, (z + offset) / zUnit];
    },
  };
}

/** From one site CRS to another */
export function between(from: SiteCrs, to: SiteCrs) {
  return (point: number[]) => to.fromRd(from.toRd(point));
}
