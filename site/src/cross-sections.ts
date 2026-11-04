// The notebooks' CrossSections widget (notebooks/cross_sections.js) on the page, on a StaticModel as the
// GeoSpeckleViewer is, with the traits the GeoBIM notebook sets: the cells of the kept SBTn zones, the
// CPTs' qc, the building's footprint, and the Color by choice above it, with a dropdown under it for the
// parameters that have more than one view.
import type { RenderProps } from "@anywidget/types";
import crossSections from "../../notebooks/cross_sections.js";
import simulationDomains from "../../notebooks/simulation_domains.json";
import { StaticModel } from "../vendor/geospeckle-viewer/static-model";
import type { Sample } from "./cpt-samples.ts";
import { type CrossSectionsModel, crossSectionTraits, quantile } from "./cross-section-traits.ts";
import { LITHOLOGY_CLASSES, legendOf } from "./geotop.ts";
import { type Grid, KEPT_ZONES, SoilModel, zoneLabel } from "./soil-model.ts";

const STATISTICS = (spread: string) => [
  { value: "median", label: "Median" },
  { value: "spread", label: `Spread (${spread})` },
];

/** What the cells can be colored by, with the radio's label, and the dropdown's views where there are some */
const PARAMETERS = [
  { key: "sbt", label: "Soil behavior type" },
  {
    key: "probability",
    label: "SBTn probability",
    views: [
      { value: "likely", label: "Most likely" },
      ...KEPT_ZONES.map((zone) => ({ value: String(zone), label: zoneLabel(zone) })),
    ],
  },
  { key: "qc", label: "qc", views: STATISTICS("P90 / P10") },
  { key: "fs", label: "fs", views: STATISTICS("P90 / P10") },
  { key: "ic", label: "Ic", views: STATISTICS("P90 − P10") },
  { key: "domain", label: "Simulation domain" },
  {
    key: "geotop",
    label: "GeoTOP",
    views: [
      { value: "unit", label: "Stratigraphic unit" },
      { value: "lithology", label: "Lithology class" },
    ],
  },
] as const;
export type Parameter = (typeof PARAMETERS)[number]["key"];

/** The parameter shown first */
const DEFAULT: Parameter = "sbt";

/**
 * The CrossSections widget in el, with the Color by choice above it. The arrays that a choice needs load
 * when it is made; the most likely zone's probability, which the hover shows, after the first paint.
 * onParameter hears each parameter chosen, the first one too.
 */
export function mountCrossSections(
  el: HTMLElement,
  soil: SoilModel,
  grid: Grid,
  samples: Sample[],
  footprint: number[][],
  onParameter: (parameter: Parameter) => void = () => {},
) {
  const { cells, traits } = crossSectionTraits(grid, samples, footprint, simulationDomains.colors);
  const model = new StaticModel<CrossSectionsModel>(traits);

  // The radio, and under it the dropdown of the chosen parameter's views, each parameter keeping its own
  const choice = document.createElement("fieldset");
  choice.className = "color-by";
  const legend = document.createElement("legend");
  legend.textContent = "Color by";
  const radios = document.createElement("div");
  radios.className = "options";
  const views = document.createElement("select");
  const status = document.createElement("span");
  status.className = "status";
  status.setAttribute("aria-live", "polite");
  const below = document.createElement("div");
  below.className = "views";
  below.append(views, status);
  const viewOf = new Map<Parameter, string>(
    PARAMETERS.flatMap((parameter) => ("views" in parameter ? [[parameter.key, parameter.views[0].value]] : [])),
  );
  let parameter: Parameter = DEFAULT;
  radios.append(
    ...PARAMETERS.map(({ key, label }) => {
      const option = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "color-by";
      input.value = key;
      input.checked = key === DEFAULT;
      input.addEventListener("change", () => {
        parameter = key;
        fillViews();
        void show();
      });
      option.append(input, ` ${label}`);
      return option;
    }),
  );
  views.addEventListener("change", () => {
    viewOf.set(parameter, views.value);
    void show();
  });
  /** The chosen parameter's views in the dropdown; its row keeps its height without any (style.css) */
  function fillViews() {
    const chosen = PARAMETERS.find(({ key }) => key === parameter)!;
    const options = "views" in chosen ? chosen.views : [];
    views.replaceChildren(...options.map(({ value, label }) => new Option(label, value)));
    views.value = viewOf.get(parameter) ?? "";
    views.setAttribute("aria-label", `${chosen.label}: what it shows`);
    views.hidden = !options.length;
  }
  fillViews();
  choice.append(legend, radios, below);
  const widget = document.createElement("div");
  el.append(choice, widget);
  crossSections.render({ model, el: widget } as unknown as RenderProps<CrossSectionsModel>);

  /** Float32 bytes of a value per kept cell */
  const perCell = (value: (index: number) => number) =>
    new DataView(Float32Array.from(cells, value).buffer);
  const asFloats = (bytes: DataView) => new Float32Array(bytes.buffer);

  /** The median or spread of qc, fs or Ic: qc and fs simulated as their log10, so P90 / P10 for them */
  async function statistic(name: "qc" | "fs" | "ic", view: string): Promise<Pick<CrossSectionsModel, "values" | "value_scale">> {
    const log = name !== "ic";
    const label = name === "ic" ? "Ic" : name;
    const unit = log ? "MPa" : undefined;
    if (view === "median") {
      const p50 = await soil.values(`${name}_p50`);
      const values = perCell((index) => p50[index]);
      const all = asFloats(values);
      return {
        values,
        value_scale: log
          ? { label: `${label} median`, unit, log, min: quantile(all, 0.02), max: quantile(all, 0.98), scheme: "viridis" }
          : { label: "Ic median", log, min: 1.31, max: 3.6, scheme: "viridis" },
      };
    }
    const [p10, p90] = await Promise.all([soil.values(`${name}_p10`), soil.values(`${name}_p90`)]);
    const values = perCell((index) => (log ? p90[index] / p10[index] : p90[index] - p10[index]));
    const all = asFloats(values);
    return {
      values,
      value_scale: log
        ? { label: `${label} P90 / P10`, log, min: quantile(all, 0.02), max: quantile(all, 0.98), scheme: "oranges" }
        : { label: "Ic P90 − P10", log, min: 0, max: quantile(all, 0.98), scheme: "oranges" },
    };
  }

  /**
   * The values of a choice and their scale, once its arrays are there. Colored by a class, the value under
   * the pointer is the probability of the most likely zone, as in the notebook.
   */
  async function valuesOf(parameter: Parameter, view: string | undefined): Promise<Pick<CrossSectionsModel, "values" | "value_scale">> {
    if (parameter === "qc" || parameter === "fs" || parameter === "ic") {
      return statistic(parameter, view ?? "median");
    }
    if (parameter === "geotop" && view === "lithology") {
      const { classes, names } = await soil.geotopLithology();
      const legend = legendOf(LITHOLOGY_CLASSES, names);
      return {
        values: perCell((index) => legend.index[classes[index]] ?? NaN),
        value_scale: { label: "GeoTOP lithology class", log: false, min: 0, max: legend.classes.length - 1, scheme: "viridis", classes: legend.classes },
      };
    }
    const probability = await soil.probability();
    if (parameter === "probability" && view !== "likely") {
      const zone = Number(view);
      return {
        values: perCell((index) => probability[zone][index]),
        value_scale: { label: `Probability of ${zoneLabel(zone)}`, log: false, min: 0, max: 1, scheme: "viridis" },
      };
    }
    return {
      values: perCell((index) => probability[grid.sbtnMostLikely[index]][index]),
      value_scale: { label: "Probability of the most likely SBTn zone", log: false, min: 0, max: 1, scheme: "viridis" },
    };
  }

  /** What the widget colors the cells by for a choice: a class at once, or the values once they are there */
  const classOf = (parameter: Parameter, view: string | undefined) =>
    parameter === "sbt" ? "lithology" : parameter === "domain" ? "domain" : parameter === "geotop" && view === "unit" ? "unit" : null;

  // A newer choice wins over one whose arrays are still loading
  let latest = 0;
  async function show() {
    const generation = ++latest;
    const view = viewOf.get(parameter);
    onParameter(parameter);
    const colorBy = classOf(parameter, view);
    // A class shows at once; the probability follows for the hover
    if (colorBy) {
      model.set("values", null);
      model.set("color_by", colorBy);
    }
    status.textContent = "Loading…";
    try {
      const { values, value_scale } = await valuesOf(parameter, view);
      if (generation !== latest) {
        return;
      }
      model.set("values", values);
      model.set("value_scale", value_scale);
      model.set("color_by", colorBy ?? "value");
      status.textContent = "";
    } catch (error) {
      console.error("The cells' values could not load", error);
      status.textContent = `Could not load: ${error}`;
    }
  }
  void show();
  return model;
}
