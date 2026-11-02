import { loadR2Model } from "./load-model";
// The bimpolars demo layout and interactions, with model traits decoded from R2 at runtime.
import { mountGeoSpeckleViewer } from "../../vendor/geospeckle-viewer/index";
import type { Basemap, FootprintMap } from "./footprint-map";
import { type Footprints, selectedFootprints } from "./footprints";
import { splitter } from "./splitter";
import { classifySamples, readReadings, samplesOf } from "../cpt-samples.ts";
import { mountCptPlot } from "../cpt-plot.ts";
import { mountCrossSections } from "../cross-sections.ts";
import { gammaMissing, SoilModel } from "../soil-model.ts";
import { viewerControls, zoneCheckboxes } from "../viewer-controls.ts";

/** m, the samples' height: the cells' */
const SAMPLE_HEIGHT = 0.25;

/** The soil's property sets, which a selected CPT layer or volume shows */
const PROPERTY_SETS = ["CPT", "SBTn volume"];

/** Their statistics' names on the card */
const STATISTICS: Record<string, string> = {
  layer: "Layer",
  qc: "qc (MPa)",
  fs: "fs (MPa)",
  rf: "Rf (%)",
  ic: "Ic",
  ic_spread: "Ic P90 − P10",
  qtn: "Qtn",
  fr: "Fr (%)",
  sbtn_probability: "Probability of the zone",
  domain: "Simulation domain",
  stratigraphic_unit: "Stratigraphic unit",
  grondsoort: "GeoTOP soil type",
  top_z: "Top (m NAP)",
  bottom_z: "Bottom (m NAP)",
  thickness: "Thickness (m)",
  samples: "Samples",
  readings: "Readings",
  cells: "Cells",
  volume_m3: "Volume (m³)",
  parts: "Parts",
  model_share: "Share of the model",
};

/** Shown in the card's title already */
const IN_THE_NAME = new Set(["bro_id", "sbtn", "sbtn_zone", "x", "y"]);

function byId<T extends HTMLElement = HTMLElement>(id: string): T {
  return document.getElementById(id) as T;
}


function paragraph(className: string, text: string): HTMLParagraphElement {
  const p = document.createElement("p");
  p.className = className;
  p.textContent = text;
  return p;
}

function level(elevation: number | null): string {
  return elevation === null ? "" : ` · level ${elevation >= 0 ? "+" : ""}${elevation.toFixed(2)} m`;
}

function format(value: unknown): string {
  if (typeof value !== "number") {
    return String(value ?? "–");
  }
  return Number.isInteger(value) ? value.toLocaleString("en") : Number(value.toPrecision(3)).toString();
}

/**
 * A property set's statistics as rows: a median with its minimum and maximum in one, a dominant
 * category with its share
 */
function statistics(set: Record<string, unknown>): HTMLDListElement {
  const list = document.createElement("dl");
  list.className = "statistics";
  for (const [key, value] of Object.entries(set)) {
    let [name, text] = [key, format(value)];
    if (key.endsWith("_median")) {
      name = key.slice(0, -"_median".length);
      text = `${format(value)} (${format(set[`${name}_min`])} – ${format(set[`${name}_max`])})`;
    } else if (key.endsWith("_dominant")) {
      name = key.slice(0, -"_dominant".length);
      text = `${format(value)} (${Math.round(Number(set[`${key}_share`]) * 100)}%)`;
    } else if (key === "model_share") {
      text = `${(Number(value) * 100).toFixed(1)}%`;
    } else if (IN_THE_NAME.has(key) || /_(min|max|share)$/.test(key)) {
      continue;
    }
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = STATISTICS[name] ?? name.replaceAll("_", " ");
    description.textContent = text;
    list.append(term, description);
  }
  return list;
}

/**
 * The card: what is selected, nothing without a selection (the header says how). A CPT layer or volume
 * shows its property set's statistics.
 */
function describe(
  card: HTMLElement,
  ids: string[],
  footprints: Footprints,
  selected: Record<string, unknown>[],
) {
  const { features, storeys } = selectedFootprints(footprints, ids);
  const lines: HTMLElement[] = [];
  const properties = (selected[0]?.properties ?? {}) as Record<string, Record<string, unknown>>;
  const set = PROPERTY_SETS.find((name) => properties[name]);
  if (ids.length === 1 && set) {
    lines.push(paragraph("class", set === "CPT" ? "Interpreted CPT layer" : "SBTn volume"));
    lines.push(paragraph("name", String(selected[0].name)));
    lines.push(statistics(properties[set]));
    card.replaceChildren(...lines);
    return;
  }
  if (ids.length === 1 && features.length === 1) {
    const { properties } = features[0];
    lines.push(paragraph("class", properties.class ?? "element"));
    lines.push(paragraph("name", properties.name ?? properties.id));
    if (properties.storey) {
      lines.push(paragraph("storey", properties.storey + level(properties.elevation)));
    }
  } else if (ids.length > 1) {
    const on = storeys.length === 1 ? "storey" : "storeys";
    lines.push(paragraph("name", `${ids.length} elements on ${storeys.length} ${on}`));
    const list = document.createElement("ul");
    for (const { properties } of features) {
      const item = document.createElement("li");
      item.textContent = `${properties.class}: ${properties.name ?? properties.id}`;
      list.appendChild(item);
    }
    lines.push(list);
  }
  if (features.length < ids.length) {
    const without = ids.length - features.length;
    lines.push(
      paragraph("hint", `${without === 1 ? "One element has" : `${without} have`} no footprint.`),
    );
  }
  card.replaceChildren(...lines);
}

/** The cross sections, then the CPT plot under them once the probabilities and Ic are there */
async function soilSections(ring: Promise<number[][]>) {
  const sectionsPane = byId("cross-sections");
  const plotPane = byId("cpt-plot");
  try {
    const soil = new SoilModel();
    const [grid, readings, gamma, footprint] = await Promise.all([
      soil.grid(),
      readReadings(),
      gammaMissing(),
      ring,
    ]);
    const all = samplesOf(readings, SAMPLE_HEIGHT);
    const { usable } = classifySamples(all, grid, SAMPLE_HEIGHT, gamma);
    sectionsPane.replaceChildren();
    const sections = mountCrossSections(sectionsPane, soil, grid, all, footprint);
    // What the sections report, for the headless test
    const report = () => {
      sectionsPane.dataset.selectedCpt = sections.get("selected_cpt") ?? "";
    };
    sections.on("change:selected_cpt", report);
    report();

    const [probability, p10, p50, p90] = await Promise.all([
      soil.probability(),
      soil.values("ic_p10"),
      soil.values("ic_p50"),
      soil.values("ic_p90"),
    ]);
    const cpts = new Map(sections.get("cpts").map((cpt) => [cpt.bro_id, cpt]));
    // A click on a CPT in the plan draws it; moving the sections does not
    const plot = mountCptPlot(
      plotPane,
      { grid, probability, ic: { p10, p50, p90 }, samples: usable },
      () => cpts.get(sections.get("selected_cpt") ?? "") ?? null,
    );
    sections.on("change:selected_cpt", plot.draw);
  } catch (error) {
    console.error("The soil model failed to load", error);
    sectionsPane.textContent = `The soil model failed to load: ${error}`;
  }
}

async function main() {
  const viewerPane = byId("viewer-pane");
  const mapPane = byId("map-pane");
  const loading = byId("loading");
  const card = byId("selection");
  const form = byId<HTMLFormElement>("layers");
  zoneCheckboxes(byId("sbtn-zones"));
  // The viewer and the map follow their panes' sizes themselves
  splitter(byId("splitter"), viewerPane.parentElement as HTMLElement);

  // Side by side only: stacked, on a phone, there is no map, and MapLibre never loads
  const sideBySide = matchMedia("(min-width: 901px)");
  const placeCard = () => (sideBySide.matches ? mapPane : viewerPane).append(card);
  sideBySide.addEventListener("change", placeCard);
  placeCard();

  const loadingModel = loadR2Model();
  void soilSections(loadingModel.then(({ ring }) => ring));
  try {
    const { state, objects, groups, footprints, outline, tiles } = await loadingModel;

    let ids: string[] = [];
    let opening: Promise<FootprintMap> | null = null;
    const openMap = () => {
      if (opening || !sideBySide.matches) {
        return;
      }
      opening = (async () => {
        const [{ FootprintMap }, { addBroLocations }] = await Promise.all([
          import("./footprint-map"),
          import("./bro-locations"),
        ]);
        const map = new FootprintMap(byId("map"), footprints, outline);
        addBroLocations(map.map);
        for (const button of document.querySelectorAll<HTMLButtonElement>(".basemaps button")) {
          button.addEventListener("click", () => {
            map.setBasemap(button.dataset.basemap as Basemap);
            for (const other of document.querySelectorAll(".basemaps button")) {
              other.setAttribute("aria-pressed", String(other === button));
            }
          });
        }
        if (ids.length) {
          map.select(ids);
        }
        return map;
      })();
    };
    sideBySide.addEventListener("change", openMap);
    openMap();

    // The viewer fills its pane: its height trait follows the pane's. The ground map starts hidden
    const { model, loaded, viewer } = mountGeoSpeckleViewer(byId("viewer"), {
      ...state,
      ground_map: {},
      objects_gz: objects,
      height: viewerPane.clientHeight,
    });
    new ResizeObserver(() => model.set("height", viewerPane.clientHeight)).observe(viewerPane);
    void tiles.catch(error => {
      console.error("3D BAG context could not load", error);
      const notice=paragraph("context-warning", `3D BAG could not load: ${error}`);
      viewerPane.append(notice);
    });

    // A click in the viewer reports the elements' applicationIds: the rows' ids
    model.on("change:selected", () => {
      const selected = model.get("selected");
      ids = selected.map((element) => element.applicationId as string);
      card.dataset.ids = JSON.stringify(ids);
      card.dataset.drawn = "[]";
      describe(card, ids, footprints, selected);
      void opening?.then((map) => {
        map.select(ids);
        // What the map draws once it is still, for the headless test (e2e/site.test.mjs)
        map.map.once("idle", () => {
          card.dataset.drawn = JSON.stringify(map.drawnSelection());
        });
      });
    });
    // What the viewer reports, for the headless test
    model.on("change:object_count", () => {
      viewerPane.dataset.objectCount = String(model.get("object_count"));
    });
    model.on("change:surroundings", () => {
      viewerPane.dataset.surroundings = JSON.stringify(model.get("surroundings"));
    });

    await loaded;
    viewerControls(form, model, await viewer, groups, state.ground_map, tiles);
    loading.hidden = true;
  } catch (error) {
    console.error("The page failed to load", error);
    loading.textContent = `The model failed to load: ${error}`;
  }
}

void main();
