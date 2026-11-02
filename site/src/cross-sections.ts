// The notebooks' CrossSections widget (notebooks/cross_sections.js) on the page, on a StaticModel as the
// GeoSpeckleViewer is, with the traits the GeoBIM notebook sets: the cells of the kept SBTn zones, the
// CPTs' qc, the building's footprint, and the Color by choice above it.
import type { RenderProps } from "@anywidget/types";
import crossSections from "../../notebooks/cross_sections.js";
import simulationDomains from "../../notebooks/simulation_domains.json";
import { StaticModel } from "../vendor/geospeckle-viewer/static-model";
import type { Sample } from "./cpt-samples.ts";
import { type CrossSectionsModel, crossSectionTraits, quantile } from "./cross-section-traits.ts";
import { type Grid, KEPT_ZONES, SoilModel, zoneLabel } from "./soil-model.ts";

/** What the cells can be colored by, with the radio's label */
const MODES = [
  { key: "lithology", label: "Most likely SBTn" },
  { key: "likelihood", label: "Its probability" },
  { key: "probability", label: "SBTn probability" },
  { key: "qc", label: "qc median" },
  { key: "ic", label: "Ic median" },
  { key: "spread", label: "Ic spread" },
  { key: "domain", label: "Simulation domain" },
] as const;
type Mode = (typeof MODES)[number]["key"];

/** The zone that SBTn probability starts with */
const DEFAULT_ZONE = 3;

/**
 * The CrossSections widget in el, with the Color by choice above it. The arrays that a mode needs load
 * when it is chosen; the most likely zone's probability, which its hover shows, after the first paint.
 */
export function mountCrossSections(
  el: HTMLElement,
  soil: SoilModel,
  grid: Grid,
  samples: Sample[],
  footprint: number[][],
) {
  const { cells, traits } = crossSectionTraits(grid, samples, footprint, simulationDomains.colors);
  const model = new StaticModel<CrossSectionsModel>(traits);

  const choice = document.createElement("fieldset");
  choice.className = "color-by";
  const legend = document.createElement("legend");
  legend.textContent = "Color by";
  const zones = document.createElement("select");
  zones.setAttribute("aria-label", "SBTn zone");
  for (const zone of KEPT_ZONES) {
    zones.add(new Option(zoneLabel(zone), String(zone), zone === DEFAULT_ZONE, zone === DEFAULT_ZONE));
  }
  const status = document.createElement("span");
  status.className = "status";
  status.setAttribute("aria-live", "polite");
  choice.append(
    legend,
    ...MODES.map(({ key, label }) => {
      const option = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "color-by";
      input.value = key;
      input.checked = key === "lithology";
      input.addEventListener("change", () => show(key));
      option.append(input, ` ${label}`);
      // The zone's dropdown, only while its probability is shown
      if (key === "probability") {
        option.append(zones);
      }
      return option;
    }),
    status,
  );
  zones.hidden = true;
  zones.addEventListener("change", () => show("probability"));
  const widget = document.createElement("div");
  el.append(choice, widget);
  crossSections.render({ model, el: widget } as unknown as RenderProps<CrossSectionsModel>);

  /** Float32 bytes of a value per kept cell */
  const perCell = (value: (index: number) => number) =>
    new DataView(Float32Array.from(cells, value).buffer);

  /** A mode's values and their scale, once its arrays are there */
  async function valuesOf(mode: Mode): Promise<Pick<CrossSectionsModel, "values" | "value_scale">> {
    if (mode === "lithology" || mode === "likelihood") {
      const probability = await soil.probability();
      return {
        values: perCell((index) => probability[grid.sbtnMostLikely[index]][index]),
        value_scale: { label: "Probability of its zone", log: false, min: 0, max: 1, scheme: "viridis" },
      };
    }
    if (mode === "probability") {
      const zone = Number(zones.value);
      const probability = (await soil.probability())[zone];
      return {
        values: perCell((index) => probability[index]),
        value_scale: { label: `Probability of ${zoneLabel(zone)}`, log: false, min: 0, max: 1, scheme: "viridis" },
      };
    }
    if (mode === "qc") {
      const qc = await soil.values("qc_p50");
      const values = perCell((index) => qc[index]);
      const all = new Float32Array(values.buffer);
      return {
        values,
        value_scale: { label: "qc median (MPa)", log: true, min: quantile(all, 0.02), max: quantile(all, 0.98), scheme: "viridis" },
      };
    }
    if (mode === "ic") {
      const ic = await soil.values("ic_p50");
      return {
        values: perCell((index) => ic[index]),
        value_scale: { label: "Ic median", log: false, min: 1.31, max: 3.6, scheme: "viridis" },
      };
    }
    if (mode === "spread") {
      const [p10, p90] = await Promise.all([soil.values("ic_p10"), soil.values("ic_p90")]);
      const values = perCell((index) => p90[index] - p10[index]);
      return {
        values,
        value_scale: { label: "Ic P90 − P10", log: false, min: 0, max: quantile(new Float32Array(values.buffer), 0.98), scheme: "oranges" },
      };
    }
    return { values: null, value_scale: null };
  }

  // A newer choice wins over one whose arrays are still loading
  let latest = 0;
  async function show(mode: Mode) {
    const generation = ++latest;
    zones.hidden = mode !== "probability";
    // The most likely zone shows at once; its probability follows for the hover
    if (mode === "lithology" || mode === "domain") {
      model.set("values", null);
      model.set("color_by", mode);
    }
    status.textContent = mode === "domain" ? "" : "Loading…";
    try {
      const { values, value_scale } = await valuesOf(mode);
      if (generation !== latest) {
        return;
      }
      model.set("values", values);
      model.set("value_scale", value_scale);
      model.set("color_by", mode === "lithology" || mode === "domain" ? mode : "value");
      status.textContent = "";
    } catch (error) {
      console.error("The cells' values could not load", error);
      status.textContent = `Could not load: ${error}`;
    }
  }
  void show("lithology");
  return model;
}
