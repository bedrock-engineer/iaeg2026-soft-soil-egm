/** The viewer's share of the panes' width in percent at first: 3 to 2 for the map */
export const DEFAULT_SHARE = 60;

/** Neither pane gets narrower than this share */
export const MIN_SHARE = 20;
export const MAX_SHARE = 100 - MIN_SHARE;

/** What an arrow key moves the separator by */
const STEP = 2;

export function clampShare(share: number): number {
  return Math.min(MAX_SHARE, Math.max(MIN_SHARE, share));
}

/**
 * The viewer's share that puts the separator's middle under the pointer.
 *
 * @param x the pointer's x
 * @param left the panes' left edge
 * @param width the panes' width, the separator's included
 * @param gutter the separator's width
 */
export function shareAt(x: number, left: number, width: number, gutter: number): number {
  return clampShare(((x - left - gutter / 2) / (width - gutter)) * 100);
}

/**
 * Makes the separator between the two panes draggable, and movable with the arrow keys, Home
 * and End; a double click puts it back. It sets the panes' `--viewer-share` and `--map-share`,
 * which style.css reads into their columns: the stacked layout below 900 px ignores them.
 */
export function splitter(separator: HTMLElement, panes: HTMLElement) {
  let share = DEFAULT_SHARE;
  let frame = 0;

  function set(next: number) {
    share = clampShare(next);
    panes.style.setProperty("--viewer-share", `${share}fr`);
    panes.style.setProperty("--map-share", `${100 - share}fr`);
    separator.setAttribute("aria-valuenow", String(Math.round(share)));
  }

  separator.setAttribute("aria-valuemin", String(MIN_SHARE));
  separator.setAttribute("aria-valuemax", String(MAX_SHARE));
  set(share);

  separator.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    // The viewer's canvas and the map would take the moves over their own panes otherwise
    separator.setPointerCapture(event.pointerId);
    document.documentElement.classList.add("resizing");
  });
  separator.addEventListener("pointermove", (event) => {
    if (!separator.hasPointerCapture(event.pointerId)) {
      return;
    }
    const { clientX } = event;
    // One layout per frame: the viewer and the map redraw on every resize
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const box = panes.getBoundingClientRect();
      set(shareAt(clientX, box.left, box.width, separator.offsetWidth));
    });
  });
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"] as const) {
    separator.addEventListener(type, () => {
      document.documentElement.classList.remove("resizing");
    });
  }
  separator.addEventListener("dblclick", () => set(DEFAULT_SHARE));
  separator.addEventListener("keydown", (event) => {
    const moves: Record<string, number> = {
      ArrowLeft: share - STEP,
      ArrowRight: share + STEP,
      Home: MIN_SHARE,
      End: MAX_SHARE,
    };
    if (event.key in moves) {
      event.preventDefault();
      set(moves[event.key]);
    }
  });
}
