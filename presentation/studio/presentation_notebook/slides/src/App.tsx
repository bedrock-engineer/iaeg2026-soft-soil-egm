/// <reference path="./marimo-studio.d.ts" />

import { Deck, Slide } from "@revealjs/react";
import { useEffect, useRef } from "react";
import type { RevealApi } from "reveal.js";
import "reveal.js/reveal.css";
import slides from "./slides.json" with { type: "json" };

const keyboardCondition = (event: KeyboardEvent) =>
  !event.composedPath().some(
    (target) =>
      target instanceof Element && target.matches("marimo-cell, marimo-output"),
  );

/** Center slides again once projected notebook content has its final size. */
const useSettledLayout = () => {
  const deck = useRef<RevealApi | null>(null);
  useEffect(() => {
    const layout = () => deck.current?.layout();
    document.addEventListener("marimo-studio:idle", layout);
    return () => document.removeEventListener("marimo-studio:idle", layout);
  }, []);
  return deck;
};

const Points = ({ points }: { points: string[] }) => (
  <ul className="points">
    {points.map((point) => <li key={point}>{point}</li>)}
  </ul>
);

const text = Object.fromEntries(slides.map((slide) => [slide.id, slide]));

/** A title with its points beside whatever the slide shows */
const Beside = (
  { id, children }: { id: string; children: React.ReactNode },
) => (
  <Slide className="content">
    <h2>{text[id].title}</h2>
    <div className="beside">
      <Points points={text[id].points} />
      <div data-visual={id} className="visual">{children}</div>
    </div>
  </Slide>
);

/** A filmed widget that fills the slide, with its title over it */
const Filmed = (
  { id, children }: { id: string; children: React.ReactNode },
) => (
  <Slide className="filmed">
    <div data-visual={id} className="visual">{children}</div>
    <h2 className="overlay">{text[id].title}</h2>
  </Slide>
);

export const App = () => {
  const deck = useSettledLayout();
  return (
    <Deck
      className="studio-deck"
      deckRef={deck}
      config={{
        width: 1920,
        height: 1080,
        margin: 0,
        center: false,
        controls: false,
        hash: true,
        keyboardCondition,
        progress: false,
        scrollActivationWidth: 0,
        transition: "none",
      }}
    >
      <Slide className="cover">
        <h1>{text.title.title}</h1>
        <p className="author">{text.title.points.join(" · ")}</p>
      </Slide>

      <Beside id="problem">
        <marimo-output value="problem_figure" />
      </Beside>

      <Slide className="content">
        <h2>{text.pipeline.title}</h2>
        <div data-visual="pipeline" className="visual placeholder">
          Pipeline diagram
        </div>
      </Slide>

      <Filmed id="data">
        <marimo-output value="data_viewer" />
      </Filmed>

      <Beside id="domains">
        <marimo-output value="domains_chart" />
      </Beside>

      <Slide className="content simulation">
        <div className="beside">
          <div>
            <h2>{text.simulation.title}</h2>
            <Points points={text.simulation.points} />
            <marimo-output value="realization" />
          </div>
          <div data-visual="simulation" className="visual">
            <marimo-output value="section_view" />
          </div>
        </div>
      </Slide>

      <Slide className="content">
        <h2>{text.uncertainty.title}</h2>
        <div data-visual="uncertainty" className="visual">
          <marimo-output value="uncertainty_chart" />
        </div>
      </Slide>

      <Slide className="filmed">
        <div data-visual="bim" className="visual placeholder">
          Placeholder: soil types removed zone by zone, under the piles
        </div>
        <h2 className="overlay">{text.bim.title}</h2>
      </Slide>

      <Beside id="close-geology">
        <div className="placeholder">Cross-section</div>
      </Beside>

      <Beside id="close-accessible">
        <div className="placeholder">Logo diagram</div>
      </Beside>

      <Beside id="close-open">
        <div className="placeholder">Open-source tools</div>
      </Beside>

      <Slide className="content">
        <h2>{text["close-qr"].title}</h2>
        <div data-visual="close-qr" className="qr">
          <marimo-output value="qr" />
        </div>
      </Slide>
    </Deck>
  );
};
