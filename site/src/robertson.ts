// `robertson` of notebooks/cpt_robertson_classification.py, step for step, so that the page classifies the
// CPT samples as the notebooks do: change them together.

/** kPa, the atmospheric pressure of the normalization, and kN/m³, the unit weight of water */
const ATMOSPHERE = 100.0;
const GAMMA_WATER = 9.81;
/** kN/m³, the limits of the unit weights, as in GeoLibPlus */
const GAMMA_LIMITS = [10.5, 22.0] as const;
/** m, how far the groundwater lies below the ground: CEMS CPT Core's default */
const GROUNDWATER_DEPTH = 1.0;

/** Robertson's soil behavior types, the normalized SBTn zones of his chart */
export const SOIL_BEHAVIOR_TYPES: Record<number, string> = {
  1: "Sensitive fine-grained",
  2: "Organic soil",
  3: "Clay",
  4: "Silt mixture",
  5: "Sand mixture",
  6: "Sand",
  7: "Dense sand to gravelly sand",
  8: "Very stiff sand to clayey sand",
  9: "Very stiff fine-grained",
};
/** Their colors, from peat's brown through clay's blue to sand's yellow */
export const SOIL_BEHAVIOR_COLORS: Record<number, string> = {
  1: "#d73027",
  2: "#8c6d31",
  3: "#2c7fb8",
  4: "#41ae76",
  5: "#c2e699",
  6: "#fee08b",
  7: "#fdae61",
  8: "#bdbdbd",
  9: "#636363",
};

/** What robertson returns per value, in qc's layout: NaN, and zone 0, where there is no value */
export interface Classified {
  gamma: Float64Array;
  totalStress: Float64Array;
  effectiveStress: Float64Array;
  qtn: Float64Array;
  fr: Float64Array;
  ic: Float64Array;
  n: Float64Array;
  zone: Int8Array;
}

const clip = (value: number, min: number, max = Infinity) =>
  // np.clip keeps NaN
  Number.isNaN(value) ? value : Math.min(Math.max(value, min), max);

/**
 * Robertson's soil behavior type of CPT values, from the top down per CPT, all CPTs at once.
 *
 * qc and fs in MPa are rows of CPTs, each z.length long and row after row, NaN without a value;
 * z in m NAP from the top down, ground per CPT in m NAP. Without u2, qt uses the hydrostatic
 * pressure and groundwater lies GROUNDWATER_DEPTH below the ground. Cells without qc or fs weigh
 * gammaMissing (kN/m³) in the vertical stress of those below them.
 *
 * - Unit weight: Robertson & Cabal (2010), within GAMMA_LIMITS.
 * - Stresses: the unit weights added up from the ground, the pore pressure hydrostatic below the
 *   groundwater.
 * - Qtn, Fr and Ic: Robertson (2009), n iterated, until it changes by less than 0.001 in every
 *   value; Qtn and Fr within the limits of his chart.
 * - Zones 2 to 7 from Ic, and zones 1, 8 and 9 from their boundaries in the chart: Robertson (2010).
 */
export function robertson(
  qc: ArrayLike<number>,
  fs: ArrayLike<number>,
  z: ArrayLike<number>,
  ground: ArrayLike<number>,
  gammaMissing = 18.0,
  coneAreaRatio = 0.8,
): Classified {
  const depth = z.length;
  const size = ground.length * depth;
  const array = () => new Float64Array(size);
  const [hydrostatic, qt, friction, gamma, totalStress, effectiveStress, net, fr] = Array.from(
    { length: 8 },
    array,
  );
  for (let row = 0; row < ground.length; row++) {
    const groundwater = ground[row] - GROUNDWATER_DEPTH;
    // Each value holds from halfway to the value above to halfway to the one below; the first from
    // the ground
    const tops = new Float64Array(depth);
    const bottoms = new Float64Array(depth);
    for (let k = 0; k < depth; k++) {
      tops[k] = Math.min(k === 0 ? ground[row] : (z[k - 1] + z[k]) / 2.0, ground[row]);
    }
    for (let k = 0; k < depth; k++) {
      bottoms[k] =
        k < depth - 1 ? tops[k + 1] : Math.min(2.0 * z[depth - 1] - tops[depth - 1], ground[row]);
    }
    // np.cumsum less each cell's own weight, as the notebook adds it up
    let sum = 0;
    for (let k = 0; k < depth; k++) {
      const i = row * depth + k;
      hydrostatic[i] = GAMMA_WATER * clip(groundwater - z[k], 0.0);
      qt[i] = clip(qc[i] * 1000.0 + hydrostatic[i] * (1.0 - coneAreaRatio), 1e-3);
      friction[i] = fs[i] * 1000.0;
      let g = clip(
        GAMMA_WATER *
          (0.27 * Math.log10((friction[i] / qt[i]) * 100.0) +
            0.36 * Math.log10(qt[i] / ATMOSPHERE) +
            1.236),
        ...GAMMA_LIMITS,
      );
      // Fs of 0 has no logarithm: the lowest unit weight
      if (g === -Infinity || friction[i] <= 0.0) {
        g = GAMMA_LIMITS[0];
      }
      gamma[i] = g;
      const weight = (Number.isNaN(g) ? gammaMissing : g) * (tops[k] - bottoms[k]);
      sum += weight;
      const above = sum - weight;
      totalStress[i] = above + (Number.isNaN(g) ? gammaMissing : g) * clip(tops[k] - z[k], 0.0);
      effectiveStress[i] = clip(totalStress[i] - hydrostatic[i], 1.0);
      net[i] = clip(qt[i] - totalStress[i], 1e-3);
      fr[i] = clip((friction[i] / net[i]) * 100.0, 0.1, 10.0);
    }
  }

  // n of all values at once, as the notebook iterates its arrays
  let n = new Float64Array(size).fill(1);
  const qtn = array();
  const ic = array();
  for (let iteration = 0; iteration < 50; iteration++) {
    const next = array();
    // np.nanmax leaves NaN out, and is NaN when all are
    let change = NaN;
    for (let i = 0; i < size; i++) {
      qtn[i] = clip((net[i] / ATMOSPHERE) * (ATMOSPHERE / effectiveStress[i]) ** n[i], 1.0, 1000.0);
      ic[i] = Math.sqrt((3.47 - Math.log10(qtn[i])) ** 2 + (Math.log10(fr[i]) + 1.22) ** 2);
      const candidate = 0.381 * ic[i] + 0.05 * (effectiveStress[i] / ATMOSPHERE) - 0.15;
      // np.minimum keeps NaN
      next[i] = Number.isNaN(candidate) ? candidate : Math.min(candidate, 1.0);
      const difference = Math.abs(next[i] - n[i]);
      if (difference > change || (Number.isNaN(change) && !Number.isNaN(difference))) {
        change = difference;
      }
    }
    n = next;
    if (change < 1e-3) {
      break;
    }
  }

  const zone = new Int8Array(size);
  const missingAsNaN = (values: Float64Array, i: number) =>
    Number.isNaN(qc[i]) || Number.isNaN(fs[i]) ? NaN : values[i];
  const result: Classified = {
    gamma: array(),
    totalStress,
    effectiveStress,
    qtn: array(),
    fr: array(),
    ic: array(),
    n: array(),
    zone,
  };
  for (let i = 0; i < size; i++) {
    const value = ic[i];
    let z = 0;
    if (value < 1.31) z = 7;
    else if (value < 2.05) z = 6;
    else if (value < 2.6) z = 5;
    else if (value < 2.95) z = 4;
    else if (value < 3.6) z = 3;
    else if (value >= 3.6) z = 2;
    if (qtn[i] < 12.0 * Math.exp(-1.4 * fr[i])) {
      z = 1;
    }
    const shifted = fr[i] - 1.0;
    const stiffBoundary = 0.005 * shifted - 0.0003 * shifted ** 2 - 0.002;
    if (fr[i] > 1.5 && stiffBoundary > 0.0 && qtn[i] > 1.0 / stiffBoundary) {
      z = fr[i] < 4.5 ? 8 : 9;
    }
    zone[i] = Number.isNaN(qc[i]) || Number.isNaN(fs[i]) ? 0 : z;
    result.gamma[i] = missingAsNaN(gamma, i);
    result.qtn[i] = missingAsNaN(qtn, i);
    result.fr[i] = missingAsNaN(fr, i);
    result.ic[i] = missingAsNaN(ic, i);
    result.n[i] = missingAsNaN(n, i);
  }
  return result;
}
