// The GeoBIM notebook's CPT plot under the sections, the Altair chart as a Vega-Lite spec: for the
// selected CPT, qc, fs or Ic of the realizations in its column of cells with its own samples, the
// probability of each zone, and the zones of its samples. A radio above it chooses the parameter, and
// follows the cross sections when they are colored by one of them. Vega loads only once the plot is drawn.
import type { TopLevelSpec } from "vega-lite";
import type { ClassifiedSample } from "./cpt-samples.ts";
import { type Grid, isKept, KEPT_ZONES, zoneColor, zoneLabel } from "./soil-model.ts";

/** The boundaries of the zones in Ic */
const IC_BANDS = [1.31, 2.05, 2.6, 2.95, 3.6];

/** What the first panel can show: the realizations' P10, P50 and P90 of a parameter with the samples' own */
export const CPT_PARAMETERS = ["qc", "fs", "ic"] as const;
export type CptParameter = (typeof CPT_PARAMETERS)[number];
const AXES: Record<CptParameter, { title: string; log: boolean; format: string }> = {
  qc: { title: "qc (MPa)", log: true, format: ".2f" },
  fs: { title: "fs (MPa)", log: true, format: ".3f" },
  ic: { title: "Ic", log: false, format: ".2f" },
};
const LABELS: Record<CptParameter, string> = { qc: "qc", fs: "fs", ic: "Ic" };

/** The P10, P50 and P90 of a parameter's realizations per cell */
export interface Percentiles {
  p10: Float32Array;
  p50: Float32Array;
  p90: Float32Array;
}
const HEIGHT = 440;
/** The panels' widths side by side, and what the y axis, the gaps and the legend take beside them */
const WIDTHS = [280, 240, 36];
const AXIS = 52;
const SPACING = 10;
const LEGEND = 190;

export interface CptPlotData {
  grid: Grid;
  probability: Float32Array[];
  /** A parameter's percentiles, read when it is first shown */
  percentiles: (parameter: CptParameter) => Promise<Percentiles>;
  /** The classified samples of all CPTs */
  samples: ClassifiedSample[];
}

/** The panels' widths for the room there is: shrunk alike, the legend under them when it is narrow */
function widths(room: number) {
  const beside = AXIS + 2 * SPACING + WIDTHS.reduce((a, b) => a + b);
  if (room >= beside + LEGEND) {
    return { widths: WIDTHS, legend: "right" as const };
  }
  const scale = Math.min(1, (room - AXIS - 2 * SPACING - WIDTHS[2] - 8) / (WIDTHS[0] + WIDTHS[1]));
  return {
    widths: [Math.floor(WIDTHS[0] * scale), Math.floor(WIDTHS[1] * scale), WIDTHS[2]],
    legend: "bottom" as const,
  };
}

/** A CPT where it is */
export interface Cpt {
  bro_id: string;
  x: number;
  y: number;
}

/** The spec for one CPT and parameter, and the caption under it */
export function cptPlotSpec(
  data: Omit<CptPlotData, "percentiles">,
  cpt: Cpt,
  room: number,
  parameter: CptParameter,
  percentiles: Percentiles,
): { spec: TopLevelSpec; caption: string } {
  const { grid } = data;
  const h = grid.cell.z;
  const { bro_id: broId, x: cptX, y: cptY } = cpt;
  const kept = data.samples.filter((s) => s.bro_id === broId && isKept(s.zone));

  // The kept cells of the column of cells the CPT lies in, from the bottom up
  const column: Array<{ index: number; z: number }> = [];
  const [nx, ny] = [grid.x.length, grid.y.length];
  grid.z.forEach((z, k) => {
    for (let j = 0; j < ny; j++) {
      if (Math.abs(grid.y[j] - cptY) > grid.cell.y / 2) continue;
      for (let i = 0; i < nx; i++) {
        const index = (k * ny + j) * nx + i;
        if (Math.abs(grid.x[i] - cptX) <= grid.cell.x / 2 && isKept(grid.sbtnMostLikely[index])) {
          column.push({ index, z });
        }
      }
    }
  });
  const realizations = column.map(({ index, z }) => ({
    z,
    p10: percentiles.p10[index],
    p50: percentiles.p50[index],
    p90: percentiles.p90[index],
  }));
  // Stacked over the kept zones; what is left to 1 is the zones left out, and stays white
  const probabilities = column.flatMap(({ index, z }) => {
    let cumulative = 0;
    return KEPT_ZONES.flatMap((zone) => {
      const p = data.probability[zone][index];
      cumulative += p;
      return p > 0
        ? [{ z, top: z + h / 2, bottom: z - h / 2, start: cumulative - p, end: cumulative, label: zoneLabel(zone), probability: p }]
        : [];
    });
  });
  const dots = kept.map((s) => ({
    z: s.z,
    top: s.z + h / 2,
    bottom: s.z - h / 2,
    label: zoneLabel(s.zone),
    value: { qc: s.qc, fs: s.fs, ic: s.ic }[parameter],
  }));
  const zs = [...column.map((c) => c.z), ...kept.map((s) => s.z)];
  const domain = [Math.min(...zs) - 0.5, Math.max(...zs) + 0.5];

  const layout = widths(room);
  const y = { field: "z", type: "quantitative", title: "z (m NAP)", scale: { domain } } as const;
  // Ic on Robertson's chart; qc and fs on a logarithmic axis over what the CPT and its column hold
  const axis = AXES[parameter];
  const shown = [...realizations.flatMap(({ p10, p90 }) => [p10, p90]), ...dots.map((dot) => dot.value ?? NaN)].filter(
    (value) => Number.isFinite(value) && value > 0,
  );
  const [low, high] = [Math.floor(Math.log10(Math.min(...shown))), Math.ceil(Math.log10(Math.max(...shown)))];
  const scale = axis.log ? { type: "log" as const, domain: [10 ** low, 10 ** high] } : { domain: [1, 4.5] };
  // A tick per decade on the logarithmic axis, whose labels would crowd a narrow panel otherwise
  const ticks = axis.log ? { axis: { values: Array.from({ length: high - low + 1 }, (_, k) => 10 ** (low + k)), format: "~g" } } : {};
  const x = (field: string) => ({ field, type: "quantitative", title: axis.title, scale, ...ticks }) as const;
  const color = {
    field: "label",
    type: "nominal",
    title: "SBTn zone",
    scale: { domain: KEPT_ZONES.map(zoneLabel), range: KEPT_ZONES.map(zoneColor) },
  } as const;
  const spec: TopLevelSpec = {
    $schema: "https://vega.github.io/schema/vega-lite/v6.json",
    hconcat: [
      {
        width: layout.widths[0],
        height: HEIGHT,
        layer: [
          ...(parameter === "ic"
            ? [
                {
                  data: { values: IC_BANDS.map((band) => ({ band })) },
                  mark: { type: "rule" as const, color: "#bbbbbb", strokeDash: [3, 3] },
                  encoding: { x: { ...x("band") } },
                },
              ]
            : []),
          {
            data: { values: realizations },
            mark: { type: "area", opacity: 0.25, color: "#4c78a8", orient: "horizontal", clip: true },
            encoding: { y, x: x("p10"), x2: { field: "p90" } },
          },
          {
            data: { values: realizations },
            mark: { type: "line", color: "#1f3b63", strokeWidth: 2, clip: true },
            encoding: { y, x: x("p50"), order: { field: "z", type: "quantitative" } },
          },
          {
            data: { values: dots },
            mark: { type: "circle", color: "black", size: 18, opacity: 1, clip: true },
            encoding: {
              y,
              x: x("value"),
              tooltip: [
                { field: "z", type: "quantitative", title: "z (m NAP)" },
                { field: "label", type: "nominal", title: "SBTn zone" },
                { field: "value", type: "quantitative", title: axis.title, format: axis.format },
              ],
            },
          },
        ],
      },
      {
        width: layout.widths[1],
        height: HEIGHT,
        data: { values: probabilities },
        mark: "rect",
        encoding: {
          x: {
            field: "start",
            type: "quantitative",
            // On two lines where the panel is narrow
            title: layout.legend === "right" ? "Probability of each SBTn zone" : ["Probability of", "each SBTn zone"],
            scale: { domain: [0, 1] },
            axis: { format: "%" },
          },
          x2: { field: "end" },
          y: { field: "bottom", type: "quantitative", scale: { domain }, axis: null },
          y2: { field: "top" },
          color,
          tooltip: [
            { field: "z", type: "quantitative", title: "z (m NAP)" },
            { field: "label", type: "nominal", title: "SBTn zone" },
            { field: "probability", type: "quantitative", title: "Probability", format: ".0%" },
          ],
        },
      },
      {
        width: layout.widths[2],
        height: HEIGHT,
        title: "CPT",
        data: { values: dots },
        mark: "rect",
        encoding: {
          x: { value: 0 },
          x2: { value: "width" },
          y: { field: "bottom", type: "quantitative", scale: { domain }, axis: null },
          y2: { field: "top" },
          color,
          tooltip: [
            { field: "z", type: "quantitative", title: "z (m NAP)" },
            { field: "label", type: "nominal", title: "SBTn zone" },
          ],
        },
      },
    ],
    spacing: SPACING,
    resolve: { scale: { y: "shared", color: "shared" } },
    config: {
      legend: { orient: layout.legend, columns: layout.legend === "right" ? 1 : 2 },
      view: { stroke: "#ddd" },
      font: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
    },
  };
  const caption =
    `${broId} at x = ${cptX.toFixed(0)}, y = ${cptY.toFixed(0)}, in the column of cells of ` +
    `${grid.cell.x} × ${grid.cell.y} m around it: ${LABELS[parameter]} of the realizations from P10 to P90 ` +
    `with their median and the CPT samples as dots, the probabilities of the zones, and the zones of the ` +
    `CPT samples.`;
  return { spec, caption };
}

/**
 * The plot of the selected CPT in el, with the parameter's radio above it and its caption under it: drawn
 * again when the CPT, the parameter or the room for it changes, never when only the sections move.
 * show(parameter) sets the radio, as the cross sections do; the radio never sets them.
 */
export function mountCptPlot(
  el: HTMLElement,
  data: CptPlotData,
  selected: () => Cpt | null,
  initial: CptParameter = "qc",
) {
  let parameter = initial;
  const choice = document.createElement("fieldset");
  choice.className = "color-by cpt-parameter";
  const legend = document.createElement("legend");
  legend.textContent = "Plot";
  const radios = document.createElement("div");
  radios.className = "options";
  const inputs = CPT_PARAMETERS.map((key) => {
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "cpt-parameter";
    input.value = key;
    input.checked = key === parameter;
    input.addEventListener("change", () => show(key));
    const option = document.createElement("label");
    option.append(input, ` ${LABELS[key]}`);
    radios.append(option);
    return input;
  });
  choice.append(legend, radios);
  const chart = document.createElement("div");
  const caption = document.createElement("p");
  caption.className = "caption";
  el.replaceChildren(choice, chart, caption);
  let shown = "";
  /** The parameter of the chart on the page */
  let plotted: CptParameter | null = null;
  let drawing: Promise<unknown> = Promise.resolve();
  let finalize: (() => void) | null = null;
  function draw() {
    const cpt = selected();
    const room = el.clientWidth;
    const key = `${cpt?.bro_id} ${parameter} ${widths(room).widths.join(" ")} ${widths(room).legend}`;
    if (!cpt || key === shown) {
      return;
    }
    shown = key;
    const drawn = parameter;
    // Its arrays may take a while the first time
    if (drawn !== plotted) {
      caption.textContent = `Loading ${LABELS[drawn]} of the cells…`;
    }
    drawing = drawing.then(async () => {
      const [{ default: embed }, percentiles] = await Promise.all([import("vega-embed"), data.percentiles(drawn)]);
      // A newer CPT, parameter or room is drawn after this one
      if (key !== shown) {
        return;
      }
      const { spec, caption: text } = cptPlotSpec(data, cpt, room, drawn, percentiles);
      finalize?.();
      const result = await embed(chart, spec, { actions: false, renderer: "svg" });
      finalize = () => result.finalize();
      plotted = drawn;
      caption.textContent = text;
    }).catch((error) => {
      console.error("The CPT plot failed", error);
      caption.textContent = `The CPT plot failed: ${error}`;
    });
  }
  /** The parameter shown, with its radio checked */
  function show(next: CptParameter) {
    parameter = next;
    for (const input of inputs) {
      input.checked = input.value === next;
    }
    draw();
  }
  new ResizeObserver(draw).observe(el);
  draw();
  return { draw, show };
}
