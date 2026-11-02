// The GeoBIM notebook's checkboxes beside its viewer, under the page's: the context, the models and the
// SBTn volumes one by one. The models stay loaded: their elements hide with the viewer's
// FilteringExtension, so that the camera stays where it is. The ground map and the 3D BAG are traits,
// set without sending the models again.
import { FilteringExtension, type Viewer } from "@speckle/viewer";
import type {
  GeoSpeckleViewerModel,
  GroundMap,
  StaticModel,
  Tileset,
} from "../vendor/geospeckle-viewer/index";
import { KEPT_ZONES, zoneColor, zoneLabel } from "./soil-model.ts";

/** The viewer ids of the elements behind each checkbox */
export interface Groups {
  architecture: string[];
  structure: string[];
  cpts: string[];
  /** Per zone */
  volumes: Map<number, string[]>;
}

/** A checkbox per kept zone with its swatch, in the SBTn group */
export function zoneCheckboxes(group: HTMLElement) {
  for (const zone of KEPT_ZONES) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    const swatch = document.createElement("span");
    input.type = "checkbox";
    input.name = `zone-${zone}`;
    input.checked = true;
    input.disabled = true;
    swatch.className = "swatch";
    swatch.style.background = zoneColor(zone);
    label.append(input, swatch, zoneLabel(zone));
    group.append(label);
  }
}

export function viewerControls(
  form: HTMLFormElement,
  model: StaticModel<GeoSpeckleViewerModel>,
  viewer: Viewer,
  groups: Groups,
  groundMap: GroundMap,
  tiles: Promise<Tileset>,
) {
  const checked = (name: string) => (form.elements.namedItem(name) as HTMLInputElement).checked;
  const filtering = viewer.createExtension(FilteringExtension);

  function showElements() {
    const hidden = [
      ...(checked("architecture") ? [] : groups.architecture),
      ...(checked("structure") ? [] : groups.structure),
      ...(checked("cpts") ? [] : groups.cpts),
      ...KEPT_ZONES.flatMap((zone) =>
        checked("volumes") && checked(`zone-${zone}`) ? [] : (groups.volumes.get(zone) ?? []),
      ),
    ];
    filtering.resetFilters();
    if (hidden.length) {
      filtering.hideObjects(hidden, undefined, true);
    }
    viewer.requestRender();
  }

  // Each its own trait, so that the one does not load the other again
  const showMap = () => model.set("ground_map", checked("map") ? groundMap : {});
  let tileset: Tileset | null = null;
  const showBuildings = () => model.set("tilesets", checked("buildings") && tileset ? [tileset] : []);
  void tiles.then(
    (loaded) => {
      tileset = loaded;
      showBuildings();
    },
    // The page says so in the viewer
    () => {},
  );

  form.addEventListener("change", (event) => {
    const name = (event.target as HTMLInputElement).name;
    if (name === "map") {
      showMap();
    } else if (name === "buildings") {
      showBuildings();
    } else {
      showElements();
    }
  });
  for (const input of form.querySelectorAll("input")) {
    input.disabled = false;
  }
  showMap();
  showElements();
}
