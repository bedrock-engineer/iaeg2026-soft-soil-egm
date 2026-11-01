import type { AnyModel } from "@anywidget/types";

// anywidget's own types: handlers of custom messages take arguments, change handlers none
// oxlint-disable-next-line typescript/no-explicit-any
type Handler = (...args: any[]) => void;

/**
 * An anywidget model without a kernel behind it, for a widget on a static page: it holds the
 * traits the page fetched, and the widget's own changes (a selection, what it reports) fire
 * `change:<trait>` as they do in a notebook, so the page can follow them. Nothing is synced:
 * save_changes and send do nothing.
 */
// oxlint-disable-next-line typescript/no-explicit-any
export class StaticModel<T extends Record<string, any>> implements AnyModel<T> {
  #values: T;
  #handlers = new Map<string, Set<Handler>>();

  constructor(values: T) {
    this.#values = { ...values };
  }

  get<K extends keyof T>(key: K): T[K] {
    return this.#values[key];
  }

  /** Sets a trait and fires `change:<trait>` and `change`, unless the value is the same one */
  set<K extends keyof T>(key: K, value: T[K]): void {
    if (Object.is(this.#values[key], value)) {
      return;
    }
    this.#values[key] = value;
    for (const event of [`change:${String(key)}`, "change"]) {
      for (const handler of this.#handlers.get(event) ?? []) {
        handler();
      }
    }
  }

  on(eventName: string, callback: Handler): void {
    const handlers = this.#handlers.get(eventName) ?? new Set();
    handlers.add(callback);
    this.#handlers.set(eventName, handlers);
  }

  /** Removes a handler, all handlers of an event, or every handler */
  off(eventName?: string | null, callback?: Handler | null): void {
    if (!eventName) {
      this.#handlers.clear();
    } else if (!callback) {
      this.#handlers.delete(eventName);
    } else {
      this.#handlers.get(eventName)?.delete(callback);
    }
  }

  save_changes(): void {}

  send(): void {}

  widget_manager = {
    get_model(): never {
      throw new Error("a static page has no other widget models");
    },
  };
}
