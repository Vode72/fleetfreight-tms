import { beforeEach, describe, expect, it } from "vitest";

import indexHtml from "../../index.html?raw";
import themeInit from "../../public/theme-init.js?raw";
import { LANGUAGE_STORAGE_KEY } from "../i18n";
import { THEME_STORAGE_KEY } from "./theme";

/** Runs the pre-paint script the way the browser would (globals, no module scope). */
function runThemeInit(): void {
  (0, eval)(themeInit);
}

describe("public/theme-init.js (pre-paint script, CSP script-src 'self')", () => {
  beforeEach(() => {
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.lang = "en";
  });

  it("is loaded from <head> as a blocking classic script, and index.html has no inline script", () => {
    const head = indexHtml.slice(indexHtml.indexOf("<head>"), indexHtml.indexOf("</head>"));
    expect(head).toMatch(/<script src="\/theme-init\.js"><\/script>/);
    const scripts = [...indexHtml.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
    expect(scripts.length).toBeGreaterThan(0);
    for (const [, attributes, body] of scripts) {
      expect(attributes).toContain("src=");
      expect(body?.trim()).toBe("");
    }
    // Blocking: no async or defer on the theme script.
    expect(head).not.toMatch(/theme-init\.js"[^>]*(async|defer)/);
  });

  it("uses the same storage keys as the app", () => {
    expect(themeInit).toContain(`"${THEME_STORAGE_KEY}"`);
    expect(themeInit).toContain(`"${LANGUAGE_STORAGE_KEY}"`);
  });

  it("applies a remembered theme and language", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "control-dark");
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "fi");
    runThemeInit();
    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    expect(document.documentElement).toHaveAttribute("lang", "fi");
  });

  it("ignores unknown stored values", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "neon");
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "xx");
    runThemeInit();
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(document.documentElement).toHaveAttribute("lang", "en");
  });
});
