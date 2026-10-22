import { ProjectMap } from "./map/map";
import { modelCentre, modelExtent } from "./project-geometry";

const repoUrl = "https://github.com/bedrock-engineer/iaeg2026-soft-soil-egm";

const nf = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });

const extentFacts: Array<[label: string, value: string]> = [
  ["Location", "Overhoeks, Amsterdam Noord"],
  [
    "Centre (RD New)",
    `${nf.format(modelCentre[0])}, ${nf.format(modelCentre[1])}`,
  ],
  [
    "x (RD New)",
    `${nf.format(modelExtent.xmin)} – ${nf.format(modelExtent.xmax)}`,
  ],
  [
    "y (RD New)",
    `${nf.format(modelExtent.ymin)} – ${nf.format(modelExtent.ymax)}`,
  ],
  [
    "Size",
    `${modelExtent.xmax - modelExtent.xmin} × ${modelExtent.ymax - modelExtent.ymin} m, ground level to ${modelExtent.zmin} m NAP`,
  ],
  ["BRO CPTs inside", "66"],
];

export function App() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 space-y-6">
      <header className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
          IAEG 2026 · 30 October 2026
        </p>
        <h1 className="text-3xl font-semibold text-balance">
          Soft Soil EGM with GemPy
        </h1>
        <p className="max-w-prose text-gray-700">
          An open-source workflow that builds a soft-soil engineering geological
          model from GeoTOP and BRO CPTs, with GemPy, and shares it in Speckle.
          The model covers a 400 × 500 m block around a fictitious building plot
          in Overhoeks, Amsterdam Noord.
        </p>
      </header>

      <ProjectMap />

      <section className="grid gap-6 md:grid-cols-[1fr_auto]">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          {extentFacts.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-gray-500">{label}</dt>
              <dd className="tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        <nav className="flex flex-col gap-1 text-sm">
          <a className="text-blue-700 hover:underline" href={repoUrl}>
            Source code on GitHub
          </a>
          <a
            className="text-blue-700 hover:underline"
            href={`${repoUrl}/issues/1`}
          >
            Project map (issue #1)
          </a>
        </nav>
      </section>

      <footer className="border-t border-gray-200 pt-3 text-xs text-gray-500">
        The GeoTOP extent is the plot centre ±200 m plus one extra 100 m GeoTOP
        row to the north. The site plot is fictitious. CPT locations from the{" "}
        <a className="hover:underline" href="https://www.broloket.nl/">
          BRO
        </a>
        . A{" "}
        <a className="hover:underline" href="https://bedrock.engineer">
          Bedrock.engineer
        </a>{" "}
        project.
      </footer>
    </div>
  );
}
