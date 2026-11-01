import { loadR2Model } from "./load-model";
import { addBroLocations } from "./bro-locations";
// The bimpolars demo layout and interactions, with model traits decoded from R2 at runtime.
import {
  type GeoSpeckleViewerModel,
  mountGeoSpeckleViewer,
} from "../../vendor/geospeckle-viewer/index";
import type { FeatureCollection } from "geojson";
import { type Basemap, FootprintMap, type Footprints, selectedFootprints } from "./footprint-map";
import { splitter } from "./splitter";


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

/** The card on the map: what is selected, nothing without a selection (the header says how) */
function describe(card: HTMLElement, ids: string[], footprints: Footprints) {
  const { features, storeys } = selectedFootprints(footprints, ids);
  const lines: HTMLElement[] = [];
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

async function main() {
  const viewerPane = byId("viewer-pane");
  const loading = byId("loading");
  const card = byId("selection");
  // The viewer and the map follow their panes' sizes themselves
  splitter(byId("splitter"), viewerPane.parentElement as HTMLElement);
  try {
    const {state,objects,footprints,outline,tiles} = await loadR2Model();

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

    // The viewer fills its pane: its height trait follows the pane's
    const { model, loaded } = mountGeoSpeckleViewer(byId("viewer"), {
      ...state,
      objects_gz: objects,
      height: viewerPane.clientHeight,
    });
    new ResizeObserver(() => model.set("height", viewerPane.clientHeight)).observe(viewerPane);
    void tiles.then(tile => model.set("tilesets", [tile])).catch(error => {
      console.error("3D BAG context could not load", error);
      const notice=paragraph("context-warning", `3D BAG could not load: ${error}`);
      viewerPane.append(notice);
    });

    // A click in the viewer reports the elements' applicationIds: the rows' ids
    model.on("change:selected", () => {
      const ids = model.get("selected").map((element) => element.applicationId as string);
      card.dataset.ids = JSON.stringify(ids);
      card.dataset.drawn = "[]";
      describe(card, ids, footprints);
      map.select(ids);
      // What the map draws once it is still, for the headless test (e2e/site.test.mjs)
      map.map.once("idle", () => {
        card.dataset.drawn = JSON.stringify(map.drawnSelection());
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
    loading.hidden = true;
  } catch (error) {
    console.error("The page failed to load", error);
    loading.textContent = `The model failed to load: ${error}`;
  }
}

void main();
