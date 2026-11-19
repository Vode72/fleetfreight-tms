import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import en from "../i18n/en.json";
import { renderApp } from "../test/renderApp";
import { DEFAULT_THEME, THEME_STORAGE_KEY, initTheme, setTheme } from "./theme";

describe("theme", () => {
  it("defaults to Business Light", () => {
    initTheme();
    expect(document.documentElement).toHaveAttribute("data-theme", DEFAULT_THEME);
  });

  it("switching the selector sets data-theme and remembers the choice", async () => {
    initTheme();
    await renderApp();

    await userEvent.selectOptions(screen.getByLabelText(en.theme.label), "control-dark");

    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("control-dark");
  });

  it("restores the remembered theme on start", async () => {
    localStorage.setItem(THEME_STORAGE_KEY, "control-dark");
    initTheme();
    await renderApp();

    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    expect(screen.getByLabelText(en.theme.label)).toHaveValue("control-dark");
  });

  it("ignores an unknown stored value", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "neon");
    initTheme();
    expect(document.documentElement).toHaveAttribute("data-theme", DEFAULT_THEME);
  });

  it("still works when storage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    initTheme();
    await renderApp();

    await userEvent.selectOptions(screen.getByLabelText(en.theme.label), "control-dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    vi.restoreAllMocks();
  });
});

describe("theme-color meta (D81)", () => {
  it("follows the theme's top bar colour", () => {
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    meta.content = "initial";
    document.head.append(meta);
    document.documentElement.style.setProperty("--panel-header", "rgb(1 2 3)");
    try {
      setTheme("control-dark");
      expect(meta.content).toBe("rgb(1 2 3)");
    } finally {
      meta.remove();
      document.documentElement.style.removeProperty("--panel-header");
    }
  });
});
