import { LOGOS, SPECKLE_LOGO } from "./logos.ts";

const NODE_HEIGHT = 124;
const LINE = 38;

/** A data artifact: a box with one or two lines of text, centered */
const Data = (
  { x, y, w, lines, dashed }: {
    x: number;
    y: number;
    w: number;
    lines: string[];
    dashed?: boolean;
  },
) => (
  <g>
    <rect
      x={x}
      y={y}
      width={w}
      height={NODE_HEIGHT}
      rx={16}
      className={dashed ? "data dashed" : "data"}
    />
    {lines.map((line, i) => (
      <text
        key={line}
        x={x + w / 2}
        y={y + NODE_HEIGHT / 2 + (i - (lines.length - 1) / 2) * LINE + 11}
        textAnchor="middle"
      >
        {line}
      </text>
    ))}
  </g>
);

/** A process: an arrow between two data artifacts, with its name over it */
const Process = (
  { x1, x2, y, lines, dashed }: {
    x1: number;
    x2: number;
    y: number;
    lines: string[];
    dashed?: boolean;
  },
) => {
  const arrowY = y + NODE_HEIGHT - 26;
  return (
    <g>
      <line
        x1={x1 + 8}
        x2={x2 - 14}
        y1={arrowY}
        y2={arrowY}
        className={dashed ? "flow dashed" : "flow"}
        markerEnd="url(#arrow)"
      />
      {lines.map((line, i) => (
        <text
          key={line}
          x={(x1 + x2) / 2}
          y={arrowY - 14 - (lines.length - 1 - i) * LINE}
          textAnchor="middle"
          className="process"
        >
          {line}
        </text>
      ))}
    </g>
  );
};

/** The whole workflow as Data → Process → Data, from the BRO to a soil type per cell */
export const Pipeline = () => {
  const [top, middle, bottom] = [64, 300, 560];
  return (
    <svg viewBox="0 0 1776 780" className="pipeline" role="img" aria-label="The workflow as a pipeline from public data to a soil type per cell">
      <defs>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="currentColor" />
        </marker>
      </defs>

      {/* The structural model, which isn't in the demo yet */}
      <Data x={0} y={top} w={300} lines={["GeoTOP voxels,", "boreholes"]} dashed />
      <Process x1={300} x2={738} y={top} lines={["GemPy", "structural model"]} dashed />
      <Data x={738} y={top} w={300} lines={["Geological model"]} dashed />
      <path
        d={`M1038,${top + NODE_HEIGHT / 2} H1257 V${middle + 18}`}
        className="flow dashed"
        markerEnd="url(#arrow)"
      />
      <text x={519} y={top - 24} textAnchor="middle" className="trigger">
        ↓ new boreholes
      </text>

      <Data x={0} y={middle} w={300} lines={["GeoTOP voxels,", "CPTs"]} />
      <Process x1={300} x2={738} y={middle} lines={["Select around", "the site"]} />
      <Data x={738} y={middle} w={300} lines={["Site voxels", "and CPTs"]} />
      <Process x1={1038} x2={1476} y={middle} lines={["Group units"]} />
      <Data x={1476} y={middle} w={300} lines={["Simulation", "domains"]} />

      {/* On to the next row */}
      <path
        d={`M1626,${middle + NODE_HEIGHT} V${bottom - 32} H2 V${bottom + NODE_HEIGHT - 26}`}
        className="flow"
        fill="none"
      />
      <Process x1={0} x2={300} y={bottom} lines={["Fit", "variograms"]} />
      <Data x={300} y={bottom} w={240} lines={["Variograms"]} />
      <Process x1={540} x2={830} y={bottom} lines={["Simulate", "qc and fs"]} />
      <Data x={830} y={bottom} w={260} lines={["Realizations"]} />
      <Process x1={1090} x2={1400} y={bottom} lines={["Classify", "(Robertson)"]} />
      <Data x={1400} y={bottom} w={376} lines={["Soil type per cell"]} />
      <text x={685} y={bottom + NODE_HEIGHT + 56} textAnchor="middle" className="trigger">
        ↑ new CPTs
      </text>
    </svg>
  );
};

const Logo = ({ name }: { name: string }) => (
  <figure className="logo">
    <svg viewBox="0 0 24 24" role="img" aria-label={name}>
      <path d={LOGOS[name].path} fill={LOGOS[name].color} />
    </svg>
    <figcaption>{name}</figcaption>
  </figure>
);

/** Open data can go anywhere, and through Speckle into any BIM software */
export const Anywhere = () => (
  <div className="anywhere">
    <div className="source">
      <strong>Open data</strong>
      <span>NetCDF</span>
      <span>GeoParquet</span>
    </div>
    <div className="routes">
      <div className="route">
        <span className="arrow">→</span>
        {["Python", "DuckDB", "QGIS", "ArcGIS"].map((name) => <Logo key={name} name={name} />)}
      </div>
      <div className="route">
        <span className="arrow">→</span>
        <img className="speckle" src={SPECKLE_LOGO} alt="Speckle" />
        <span className="arrow">→</span>
        <div className="bim">
          {["Revit", "Rhino", "AutoCAD", "Archicad", "SketchUp", "Blender"].map((name) => <Logo key={name} name={name} />)}
        </div>
      </div>
    </div>
  </div>
);

/** The open-source tools the workflow is made of */
export const Tools = () => (
  <ul className="tools">
    {["GemPy", "GSTools", "marimo", "xarray", "Polars", "bimpolars", "Speckle"].map((tool) => <li key={tool}>{tool}</li>)}
  </ul>
);
