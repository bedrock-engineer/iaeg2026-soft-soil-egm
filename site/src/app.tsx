import { useEffect, useState } from "react";
import { ProjectMap } from "./map/map";
import { geotopCells, loadBuildingFootprint, modelExtent, modelParquetUrl } from "./project-geometry";

const repoUrl = "https://github.com/bedrock-engineer/iaeg2026-soft-soil-egm";
const nf = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
const width = modelExtent.xmax - modelExtent.xmin;
const height = modelExtent.ymax - modelExtent.ymin;
const extentFacts: Array<[label: string, value: string]> = [
  ["Location", "Overhoeks, Amsterdam Noord"],
  ["Plot centre (RD New)", `${nf.format(modelExtent.centre_x)}, ${nf.format(modelExtent.centre_y)}`],
  ["x (RD New)", `${nf.format(modelExtent.xmin)} – ${nf.format(modelExtent.xmax)}`],
  ["y (RD New)", `${nf.format(modelExtent.ymin)} – ${nf.format(modelExtent.ymax)}`],
  ["Model size", `${width} × ${height} m`],
  ["Model base", `${modelExtent.zmin_nap} m NAP`],
  ["GeoTOP columns", `${geotopCells.features.length} · 100 × 100 m`],
];

export function App() {
  const [footprint, setFootprint] = useState<GeoJSON.Feature<GeoJSON.Polygon>>();
  const [loadError, setLoadError] = useState<string>();
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active=true;
    setLoadError(undefined);
    void loadBuildingFootprint().then(value=>{if(active)setFootprint(value);}).catch(error=>{if(active)setLoadError(error instanceof Error ? error.message : String(error));});
    return ()=>{active=false;};
  },[attempt]);
  const [introOpen, setIntroOpen] = useState(() => window.matchMedia("(min-width: 901px)").matches);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 901px)");
    const update = () => setIntroOpen(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return (
    <div className="project-app">
      <header className="project-bar">
        <details className="project-intro" open={introOpen} onToggle={(event) => setIntroOpen(event.currentTarget.open)}>
          <summary><h1>Soft Soil EGM with GemPy</h1></summary>
          <p>An open-source workflow from GeoTOP and BRO ground investigation data to an engineering geological model, shared in Speckle.</p>
        </details>
        <a className="source-link" href={repoUrl}>Source on GitHub <span aria-hidden="true">↗</span></a>
      </header>
      <main className="project-workspace">
        <aside className="project-context" aria-label="About the model">
          <p className="project-kicker">IAEG 2026 · 30 October 2026</p>
          <h2>Amsterdam Noord</h2>
          <p className="project-description">A {width} × {height} m block around a BIM model in Overhoeks. Explore the geological model extent alongside the ground investigations that inform it.</p>
          <section className="project-facts" aria-labelledby="extent-heading">
            <h3 id="extent-heading">Model extent</h3>
            <dl>{extentFacts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
          </section>
          <section className="project-data" aria-labelledby="data-heading">
            <h3 id="data-heading">Ground investigation</h3>
            <p>Cone penetration tests (CPT), geotechnical boreholes (BHR-GT), and geological boreholes (BHR-G) from the BRO.</p>
            <p>CPTs inside the model extent are highlighted in violet. Hover over a point to see its BRO ID, depth, and available quality information.</p>
            <a href="https://r2.eu.bedrock.engineer/bro_locations.pmtiles">BRO location data <span aria-hidden="true">↗</span></a>
          </section>
          <nav className="project-links" aria-label="Project links">
            <a href={`${repoUrl}/issues/1`}>Project plan <span aria-hidden="true">↗</span></a>
            <a href="https://www.broloket.nl/">BROloket <span aria-hidden="true">↗</span></a>
          </nav>
          <footer className="project-footer">Building footprint read directly from the <a href={modelParquetUrl}>R2 Parquet</a>.<br/>A <a href="https://bedrock.engineer">Bedrock.engineer</a> project.</footer>
        </aside>
        <section className="project-map-pane" aria-label="GeoTOP extent and BRO ground investigations">
          <div className="project-map-caption"><span>GeoTOP & ground investigation</span><span>Hover to inspect · use the layers panel to compare</span></div>
          {footprint ? <ProjectMap footprint={footprint} /> : <div className="model-loading" role="status">
            {loadError ? <><p>Could not load the R2 model: {loadError}</p><button type="button" onClick={()=>setAttempt(value=>value+1)}>Retry loading</button></> : <p>Loading BIM footprint from R2 Parquet…</p>}
          </div>}
        </section>
      </main>
    </div>
  );
}
