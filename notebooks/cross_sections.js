// GeoTOP voxels from above at one level (the plan), with a west–east section above it and a
// south–north section to its right, both through the column under the red dot. The sections fold
// out of the plan, so the ground surface is on their outer side. Drag in the plan to move the
// sections, and drag in a section to change the plan's level. CPTs show as dots in the plan and,
// in the sections, as one qc profile per column they cross: the median of the column's CPTs in a
// band from their 10th to their 90th percentile. A CPT under the pointer in the plan shows its own
// qc. The voxels are coloured by their simulation domain, stratigraphic unit or lithology class.

const SECTION = 180; // px, the depth of the sections
const GAP = 12;
const LEFT = 64;
const BOTTOM = 40;
const TOP = 8;
const RIGHT = 8;
const MAX_PLAN = 560;
const COLUMN = 100; // m, GeoTOP's columns
const VOXEL = 0.5; // m, GeoTOP's voxel height
const QC_METRES = 2.5; // m along a section per MPa of qc: a column is 40 MPa wide
const NOT_SIMULATED = "#e8e8e8";
const RED = "#d62728";
const BLUE = "#1f77b4";
const CPT_BLUE = "#08519c";
const CPT_PICK_PX = 6;
/** What the voxels can be coloured by, with its button's label */
const COLOR_BY = { domain: "Simulation domain", unit: "Stratigraphic unit", lithology: "Lithology class" };

function ticks(min, max, target) {
  const raw = (max - min) / target;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((factor) => factor * power).find((candidate) => candidate >= raw);
  const values = [];
  for (let value = Math.ceil(min / step) * step; value <= max; value += step) {
    values.push(Math.round(value * 1e6) / 1e6);
  }
  return values;
}

/**
 * One qc profile per column for the CPTs in a section: per level, the median qc of the column's
 * CPTs and their 10th and 90th percentiles, from the top down. axis is the coordinate along the
 * section.
 */
function profiles(cpts, axis) {
  const columns = new Map();
  for (const cpt of cpts) {
    const start = Math.floor(cpt[axis] / COLUMN) * COLUMN;
    const levels = columns.get(start) ?? new Map();
    columns.set(start, levels);
    cpt.z.forEach((z, k) => levels.set(z, [...(levels.get(z) ?? []), cpt.qc[k]]));
  }
  return [...columns].map(([start, levels]) => [
    start,
    [...levels]
      .sort(([a], [b]) => b - a)
      .map(([z, qcs]) => {
        qcs.sort((a, b) => a - b);
        const quantile = (p) => qcs[Math.round(p * (qcs.length - 1))];
        return { z, p10: quantile(0.1), p50: quantile(0.5), p90: quantile(0.9) };
      }),
  ]);
}

/** text in lines of at most width px */
function wrap(ctx, text, width) {
  const lines = [];
  let line = "";
  for (const word of text.split(" ")) {
    const candidate = line ? `${line} ${word}` : word;
    if (line && ctx.measureText(candidate).width > width) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  return line ? [...lines, line] : lines;
}

function render({ model, el }) {
  const root = document.createElement("div");
  root.style.cssText = "font: 12px sans-serif; user-select: none; width: 100%; color: #333;";
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "display: block; touch-action: none; background: white;";
  const legend = document.createElement("div");
  legend.style.cssText = `display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 6px 0 0 ${LEFT}px;`;
  // Buttons to colour the voxels by their simulation domain, stratigraphic unit or lithology class
  const toolbar = document.createElement("div");
  toolbar.style.cssText = `display: flex; align-items: center; gap: 6px; margin: 0 0 6px ${LEFT}px;`;
  const buttons = Object.entries(COLOR_BY).map(([mode, label]) => {
    const button = document.createElement("button");
    button.textContent = label;
    button.addEventListener("click", () => {
      model.set("color_by", mode);
      model.save_changes();
    });
    return [mode, button];
  });
  toolbar.append("Colour by", ...buttons.map(([, button]) => button));
  function styleButtons() {
    for (const [mode, button] of buttons) {
      const on = model.get("color_by") === mode;
      button.style.cssText =
        `font: 12px sans-serif; padding: 2px 10px; border-radius: 3px; cursor: pointer; ` +
        `border: 1px solid ${on ? BLUE : "#bbb"}; background: ${on ? BLUE : "white"}; color: ${on ? "white" : "#333"};`;
    }
  }
  root.append(toolbar, canvas, legend);
  el.appendChild(root);
  const ctx = canvas.getContext("2d");

  let grid = null;
  let layout = null;
  let hover = null;
  let hoverCpt = null;
  let dragging = null;

  // The voxels by position, and the model's extent: x and y are a column's south-west corner, z a
  // voxel's centre
  function index() {
    const voxels = model.get("voxels");
    const at = new Map();
    const extent = { xmin: Infinity, xmax: -Infinity, ymin: Infinity, ymax: -Infinity, zmin: Infinity, zmax: -Infinity };
    voxels.forEach(([x, y, z], i) => {
      at.set(`${x},${y},${z}`, i);
      extent.xmin = Math.min(extent.xmin, x);
      extent.xmax = Math.max(extent.xmax, x + COLUMN);
      extent.ymin = Math.min(extent.ymin, y);
      extent.ymax = Math.max(extent.ymax, y + COLUMN);
      extent.zmin = Math.min(extent.zmin, z - VOXEL / 2);
      extent.zmax = Math.max(extent.zmax, z + VOXEL / 2);
    });
    grid = { voxels, at, ...extent };
  }

  // The panels in px: the plan at one scale for x and y, the sections SECTION px deep
  function place() {
    const width = Math.max(root.clientWidth, 400);
    const { xmin, xmax, ymin, ymax } = grid;
    const s = Math.min((width - LEFT - GAP - SECTION - RIGHT) / (xmax - xmin), MAX_PLAN / (ymax - ymin));
    const w = (xmax - xmin) * s;
    const h = (ymax - ymin) * s;
    const top = { x: LEFT, y: TOP, w, h: SECTION };
    const plan = { x: LEFT, y: TOP + SECTION + GAP, w, h };
    const side = { x: LEFT + w + GAP, y: plan.y, w: SECTION, h };
    const corner = { x: side.x, y: TOP, w: SECTION, h: SECTION };
    layout = { s, top, plan, side, corner, width: side.x + SECTION + RIGHT, height: plan.y + h + BOTTOM };
    const ratio = window.devicePixelRatio || 1;
    canvas.width = layout.width * ratio;
    canvas.height = layout.height * ratio;
    canvas.style.width = `${layout.width}px`;
    canvas.style.height = `${layout.height}px`;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  // From the world to px and back. The top section shares the plan's x, the side section its y.
  const X = (x) => layout.plan.x + (x - grid.xmin) * layout.s;
  const Y = (y) => layout.plan.y + (grid.ymax - y) * layout.s;
  const topZ = (z) => layout.top.y + ((grid.zmax - z) / (grid.zmax - grid.zmin)) * layout.top.h;
  const sideZ = (z) => layout.side.x + ((z - grid.zmin) / (grid.zmax - grid.zmin)) * layout.side.w;
  const xAt = (px) => grid.xmin + (px - layout.plan.x) / layout.s;
  const yAt = (py) => grid.ymax - (py - layout.plan.y) / layout.s;
  const zAtTop = (py) => grid.zmax - ((py - layout.top.y) / layout.top.h) * (grid.zmax - grid.zmin);
  const zAtSide = (px) => grid.zmin + ((px - layout.side.x) / layout.side.w) * (grid.zmax - grid.zmin);
  const column = (value) => Math.floor(value / COLUMN) * COLUMN;
  const level = (z) => Math.round(z / VOXEL) * VOXEL;
  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  function line(x1, y1, x2, y2) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  function dot(x, y, radius, fill, stroke) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  // A column's qc profile: the band between the 10th and 90th percentiles, the median as a line
  // and a faint line at qc = 0. at places a qc at a level in px.
  function drawProfile(profile, at) {
    ctx.beginPath();
    for (const { z, p90 } of profile) {
      ctx.lineTo(...at(p90, z));
    }
    for (const { z, p10 } of [...profile].reverse()) {
      ctx.lineTo(...at(p10, z));
    }
    ctx.closePath();
    ctx.fillStyle = "rgba(0, 0, 0, 0.2)";
    ctx.fill();
    ctx.strokeStyle = "rgba(0, 0, 0, 0.35)";
    ctx.lineWidth = 1;
    line(...at(0, profile[0].z), ...at(0, profile[profile.length - 1].z));
    drawTrace(profile, at, "#000", 1.2);
  }

  function drawTrace(profile, at, color = CPT_BLUE, width = 1.5) {
    ctx.beginPath();
    for (const { z, p50 } of profile) {
      ctx.lineTo(...at(p50, z));
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
  }

  function clipped(panel, drawing) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(panel.x, panel.y, panel.w, panel.h);
    ctx.clip();
    drawing();
    ctx.restore();
  }

  function draw() {
    if (!grid || !layout) {
      return;
    }
    const { s, top, plan, side, corner } = layout;
    const x0 = model.get("x");
    const y0 = model.get("y");
    const z0 = model.get("z");
    const domainOf = model.get("domain_of");
    const domains = model.get("domains");
    const color = voxelColor();
    ctx.clearRect(0, 0, layout.width, layout.height);
    for (const panel of [top, plan, side]) {
      ctx.fillStyle = "#f6f6f6";
      ctx.fillRect(panel.x, panel.y, panel.w, panel.h);
    }

    // The voxels: in the plan those at the level, in the sections those in their row and column.
    // A fraction of a px more than their size closes the seams between them.
    const cell = COLUMN * s;
    const topVoxel = (VOXEL / (grid.zmax - grid.zmin)) * top.h;
    const sideVoxel = (VOXEL / (grid.zmax - grid.zmin)) * side.w;
    grid.voxels.forEach(([x, y, z], i) => {
      ctx.fillStyle = color(i);
      if (z === z0) {
        ctx.fillRect(X(x), Y(y + COLUMN), cell + 0.5, cell + 0.5);
      }
      if (y === y0) {
        ctx.fillRect(X(x), topZ(z + VOXEL / 2), cell + 0.5, topVoxel + 0.5);
      }
      if (x === x0) {
        ctx.fillRect(sideZ(z - VOXEL / 2), Y(y + COLUMN), sideVoxel + 0.5, cell + 0.5);
      }
    });

    // GeoTOP's columns in the plan
    ctx.strokeStyle = "rgba(255, 255, 255, 0.7)";
    ctx.lineWidth = 0.5;
    for (let x = grid.xmin; x <= grid.xmax; x += COLUMN) {
      line(X(x), plan.y, X(x), plan.y + plan.h);
    }
    for (let y = grid.ymin; y <= grid.ymax; y += COLUMN) {
      line(plan.x, Y(y), plan.x + plan.w, Y(y));
    }

    // Where the sections run in the plan, and where they cross each other in the sections
    const cx = X(x0 + COLUMN / 2);
    const cy = Y(y0 + COLUMN / 2);
    ctx.strokeStyle = BLUE;
    ctx.lineWidth = 2;
    line(plan.x, cy, plan.x + plan.w, cy);
    line(cx, plan.y, cx, plan.y + plan.h);
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    line(cx, top.y, cx, top.y + top.h);
    line(side.x, cy, side.x + side.w, cy);
    ctx.setLineDash([]);

    // The CPTs: dots in the plan, black in the sections' row and column. In the top section qc
    // runs east from a column's west edge, in the side section north from its south edge.
    const cpts = model.get("cpts");
    const inRow = cpts.filter((cpt) => column(cpt.y) === y0);
    const inColumn = cpts.filter((cpt) => column(cpt.x) === x0);
    for (const cpt of cpts) {
      const crossed = column(cpt.y) === y0 || column(cpt.x) === x0;
      dot(X(cpt.x), Y(cpt.y), crossed ? 2.5 : 1.8, crossed ? "#000" : "rgba(0, 0, 0, 0.45)");
    }
    const qcPx = QC_METRES * s;
    const atTop = (start) => (qc, z) => [X(start) + qc * qcPx, topZ(z)];
    const atSide = (start) => (qc, z) => [sideZ(z), Y(start) - qc * qcPx];
    clipped(top, () => {
      for (const [start, profile] of profiles(inRow, "x")) {
        drawProfile(profile, atTop(start));
      }
    });
    clipped(side, () => {
      for (const [start, profile] of profiles(inColumn, "y")) {
        drawProfile(profile, atSide(start));
      }
    });

    // The CPT under the pointer in the plan: its own qc, in the sections that cross its column
    const hovered = cpts[hoverCpt];
    if (hovered) {
      dot(X(hovered.x), Y(hovered.y), 4, CPT_BLUE, "white");
      const trace = hovered.z.map((z, k) => ({ z, p50: hovered.qc[k] }));
      if (column(hovered.y) === y0) {
        clipped(top, () => drawTrace(trace, atTop(column(hovered.x))));
      }
      if (column(hovered.x) === x0) {
        clipped(side, () => drawTrace(trace, atSide(column(hovered.y))));
      }
    }

    // The plan's level in the sections
    ctx.strokeStyle = RED;
    ctx.lineWidth = 1.5;
    line(top.x, topZ(z0), top.x + top.w, topZ(z0));
    line(sideZ(z0), side.y, sideZ(z0), side.y + side.h);

    ctx.strokeStyle = "#999";
    ctx.lineWidth = 1;
    for (const panel of [top, plan, side]) {
      ctx.strokeRect(panel.x, panel.y, panel.w, panel.h);
    }

    // The handles
    dot(cx, cy, 7, RED, "white");
    for (const [hx, hy] of [
      [top.x, topZ(z0)],
      [top.x + top.w, topZ(z0)],
      [sideZ(z0), side.y],
      [sideZ(z0), side.y + side.h],
    ]) {
      dot(hx, hy, 6, RED, "white");
    }

    // The axes
    ctx.fillStyle = "#333";
    ctx.font = "11px sans-serif";
    ctx.textBaseline = "middle";
    ctx.textAlign = "right";
    for (const y of ticks(grid.ymin, grid.ymax, 5)) {
      ctx.fillText(String(y), plan.x - 4, Y(y));
    }
    for (const z of ticks(grid.zmin, grid.zmax, 4)) {
      ctx.fillText(String(z), top.x - 4, topZ(z));
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const x of ticks(grid.xmin, grid.xmax, 5)) {
      ctx.fillText(String(x), X(x), plan.y + plan.h + 4);
    }
    for (const z of ticks(grid.zmin, grid.zmax, 3)) {
      ctx.fillText(String(z), sideZ(z), side.y + side.h + 4);
    }
    ctx.fillText("x (RD, m)", plan.x + plan.w / 2, plan.y + plan.h + 20);
    ctx.fillText("z (m NAP)", side.x + side.w / 2, side.y + side.h + 20);
    for (const [text, y] of [
      ["y (RD, m)", plan.y + plan.h / 2],
      ["z (m NAP)", top.y + top.h / 2],
    ]) {
      ctx.save();
      ctx.translate(10, y);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(text, 0, 0);
      ctx.restore();
    }

    // Where the plan and sections are, and the voxel under the pointer
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    const lines = [
      `Plan at z = ${z0.toFixed(1)} m NAP`,
      `W–E section at y = ${y0}–${y0 + COLUMN}`,
      `S–N section at x = ${x0}–${x0 + COLUMN}`,
    ];
    if (hovered) {
      lines.push(
        "",
        `CPT ${hovered.bro_id}`,
        `z ${hovered.z[0].toFixed(1)} to ${hovered.z[hovered.z.length - 1].toFixed(1)} m NAP`,
      );
    }
    // The hovered voxel's domain, in bold
    let bold = -1;
    if (hover !== null) {
      const [x, y, z, unit, lithology] = grid.voxels[hover];
      bold = lines.length + 1;
      lines.push(
        "",
        domains[domainOf[hover]]?.name ?? "not simulated",
        ...wrap(ctx, model.get("units")[unit].name, corner.w - 12),
        model.get("lithologies")[lithology].name,
        `x ${x}–${x + COLUMN}, y ${y}–${y + COLUMN}`,
        `z ${z.toFixed(1)} m NAP`,
      );
    }
    lines.forEach((text, k) => {
      ctx.font = k === bold ? "bold 11px sans-serif" : "11px sans-serif";
      ctx.fillText(text, corner.x + 6, corner.y + 4 + k * 14);
    });
  }

  // Each voxel's colour: its domain's (grey where it is not simulated), its stratigraphic unit's or
  // its lithology class's
  function voxelColor() {
    const voxels = grid.voxels;
    if (model.get("color_by") === "unit") {
      const units = model.get("units");
      return (i) => units[voxels[i][3]].color;
    }
    if (model.get("color_by") === "lithology") {
      const lithologies = model.get("lithologies");
      return (i) => lithologies[voxels[i][4]].color;
    }
    const domainOf = model.get("domain_of");
    const domains = model.get("domains");
    return (i) => domains[domainOf[i]]?.color ?? NOT_SIMULATED;
  }

  // The classes of what the voxels are coloured by; a stratigraphic unit by its code, with its
  // name on hover
  function fillLegend() {
    const classes = {
      unit: model.get("units").map(({ code, name, color }) => ({ name: code, title: name, color })),
      lithology: model.get("lithologies"),
    }[model.get("color_by")] ?? [...model.get("domains"), { name: "not simulated", color: NOT_SIMULATED }];
    const items = classes.map(({ name, title, color }) => {
      const item = document.createElement("span");
      const swatch = document.createElement("span");
      swatch.style.cssText = `display: inline-block; width: 12px; height: 12px; background: ${color}; vertical-align: middle; margin-right: 4px; border: 1px solid #bbb;`;
      item.append(swatch, name);
      item.title = title ?? name;
      return item;
    });
    const cpt = document.createElement("span");
    cpt.textContent =
      `● CPT. In the sections, per column: the median qc of its CPTs, in a band from their 10th to ` +
      `90th percentile (${COLUMN / QC_METRES} MPa per column width). Hover over a CPT in the plan for its own qc.`;
    legend.replaceChildren(...items, cpt);
  }

  // The panel, column and level under the pointer
  function locate(px, py) {
    const inside = (panel) => px >= panel.x && px <= panel.x + panel.w && py >= panel.y && py <= panel.y + panel.h;
    if (inside(layout.plan)) {
      return { panel: "plan", x: column(xAt(px)), y: column(yAt(py)), z: model.get("z") };
    }
    if (inside(layout.top)) {
      return { panel: "top", x: column(xAt(px)), y: model.get("y"), z: level(zAtTop(py)) };
    }
    if (inside(layout.side)) {
      return { panel: "side", x: model.get("x"), y: column(yAt(py)), z: level(zAtSide(px)) };
    }
    return null;
  }

  // The position changes here while a handle is dragged, and goes to Python when it is let go
  function set(values) {
    for (const [name, value] of Object.entries(values)) {
      if (model.get(name) !== value) {
        model.set(name, value);
      }
    }
  }

  function move(event) {
    const bounds = canvas.getBoundingClientRect();
    const px = event.clientX - bounds.left;
    const py = event.clientY - bounds.top;
    const zLimits = [grid.zmin + VOXEL / 2, grid.zmax - VOXEL / 2];
    if (dragging === "plan") {
      set({
        x: clamp(column(xAt(px)), grid.xmin, grid.xmax - COLUMN),
        y: clamp(column(yAt(py)), grid.ymin, grid.ymax - COLUMN),
      });
    } else if (dragging === "top") {
      set({ z: clamp(level(zAtTop(py)), ...zLimits) });
    } else if (dragging === "side") {
      set({ z: clamp(level(zAtSide(px)), ...zLimits) });
    }
    const spot = locate(px, py);
    canvas.style.cursor = { plan: "move", top: "ns-resize", side: "ew-resize" }[dragging ?? spot?.panel] ?? "default";
    hover = spot ? (grid.at.get(`${spot.x},${spot.y},${spot.z}`) ?? null) : null;
    // The CPT nearest the pointer in the plan, within CPT_PICK_PX
    hoverCpt = null;
    if (spot?.panel === "plan" && !dragging) {
      let nearest = CPT_PICK_PX;
      model.get("cpts").forEach((cpt, i) => {
        const distance = Math.hypot(X(cpt.x) - px, Y(cpt.y) - py);
        if (distance < nearest) {
          nearest = distance;
          hoverCpt = i;
        }
      });
    }
    draw();
  }

  canvas.addEventListener("pointerdown", (event) => {
    const bounds = canvas.getBoundingClientRect();
    const spot = locate(event.clientX - bounds.left, event.clientY - bounds.top);
    if (!spot) {
      return;
    }
    dragging = spot.panel;
    canvas.setPointerCapture(event.pointerId);
    move(event);
  });
  canvas.addEventListener("pointermove", move);
  for (const name of ["pointerup", "pointercancel"]) {
    canvas.addEventListener(name, () => {
      if (dragging) {
        model.save_changes();
      }
      dragging = null;
    });
  }
  canvas.addEventListener("pointerleave", () => {
    if (!dragging) {
      hover = null;
      hoverCpt = null;
      draw();
    }
  });

  for (const name of ["x", "y", "z", "domain_of", "cpts"]) {
    model.on(`change:${name}`, draw);
  }
  for (const name of ["domains", "units", "lithologies", "color_by"]) {
    model.on(`change:${name}`, () => {
      styleButtons();
      fillLegend();
      draw();
    });
  }
  model.on("change:voxels", () => {
    index();
    place();
    draw();
  });

  index();
  place();
  styleButtons();
  fillLegend();
  draw();
  const resizing = new ResizeObserver(() => {
    place();
    draw();
  });
  resizing.observe(root);
  return () => resizing.disconnect();
}

export default { render };
