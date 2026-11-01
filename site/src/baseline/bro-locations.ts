import { addProtocol, type Map as MapLibreMap, Popup } from "maplibre-gl";
import { Protocol } from "pmtiles";

const protocol = new Protocol();
addProtocol("pmtiles", protocol.tile);
const layers = [
  { id: "cpt", label: "CPT", color: "#2563eb" },
  { id: "bhrgt", label: "Borehole (BHR-GT)", color: "#ea580c" },
  { id: "bhrg", label: "Borehole (BHR-G)", color: "#16a34a" },
];
export function addBroLocations(map: MapLibreMap) {
  const panel = document.createElement("details");
  panel.className = "bro-layers";
  panel.innerHTML = "<summary>BRO ground investigation</summary>";
  for (const layer of layers) {
    const label = document.createElement("label"),
      input = document.createElement("input"),
      swatch = document.createElement("span");
    input.type = "checkbox";
    input.checked = true;
    swatch.style.background = layer.color;
    label.append(input, swatch, document.createTextNode(layer.label));
    panel.append(label);
    input.addEventListener("change", () => {
      for (const id of [layer.id + "-points", layer.id + "-clusters"])
        if (map.getLayer(id))
          map.setLayoutProperty(
            id,
            "visibility",
            input.checked ? "visible" : "none",
          );
    });
  }
  map.getContainer().parentElement!.append(panel);
  const ready = () => {
    map.addSource("bro", {
      type: "vector",
      url: "pmtiles://https://r2.eu.bedrock.engineer/bro_locations.pmtiles",
      attribution: "BRO",
    });
    const canvas = document.createElement("canvas");
    canvas.width = 28;
    canvas.height = 28;
    const c = canvas.getContext("2d")!;
    c.beginPath();
    c.moveTo(2, 2);
    c.lineTo(26, 2);
    c.lineTo(14, 26);
    c.closePath();
    c.fillStyle = "#2563eb";
    c.fill();
    c.strokeStyle = "#fff";
    c.lineWidth = 2;
    c.stroke();
    map.addImage("bro-cpt", c.getImageData(0, 0, 28, 28), { pixelRatio: 2 });
    for (const layer of layers) {
      map.addLayer({
        id: layer.id + "-clusters",
        type: "circle",
        source: "bro",
        "source-layer": layer.id,
        filter: ["has", "point_count"],
        paint: {
          "circle-color": layer.color,
          "circle-opacity": 0.6,
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["sqrt", ["get", "point_count"]],
            1.4,
            5,
            30,
            15,
            200,
            22,
          ],
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 1,
        },
      });
      if (layer.id === "cpt")
        map.addLayer({
          id: layer.id + "-points",
          type: "symbol",
          source: "bro",
          "source-layer": layer.id,
          filter: ["!", ["has", "point_count"]],
          layout: {
            "icon-image": "bro-cpt",
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
          },
        });
      else
        map.addLayer({
          id: layer.id + "-points",
          type: "circle",
          source: "bro",
          "source-layer": layer.id,
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-color": layer.color,
            "circle-radius": 4,
            "circle-stroke-color": "#fff",
            "circle-stroke-width": 1,
          },
        });
    }
    const popup = new Popup({ closeButton: false, closeOnClick: false });
    const ids = layers.flatMap((l) => [l.id + "-points", l.id + "-clusters"]);
    map.on("mousemove", (event) => {
      const f = map.queryRenderedFeatures(event.point, { layers: ids })[0];
      if (!f) {
        popup.remove();
        map.getCanvas().style.cursor = "";
        return;
      }
      const p = f.properties;
      const node = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = p.bro_id ?? `${p.point_count} locations — zoom in`;
      node.append(name);
      for (const text of [
        p.depth != null ? `Depth: ${p.depth} m` : "",
        [p.quality, p.quality_class, p.year].filter(Boolean).join(" · "),
      ])
        if (text) {
          const line = document.createElement("div");
          line.textContent = text;
          node.append(line);
        }
      popup.setLngLat(event.lngLat).setDOMContent(node).addTo(map);
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseout", () => popup.remove());
  };
  if (map.isStyleLoaded()) ready();
  else map.once("load", ready);
}
