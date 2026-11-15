import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import indexHtml from "../../index.html?raw";
import { LANGUAGE_STORAGE_KEY, setLanguage } from "../i18n";
import en from "../i18n/en.json";
import fi from "../i18n/fi.json";
import { renderApp } from "../test/renderApp";

describe("language selector", () => {
  it("defaults to English", () => {
    renderApp();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(en.dashboard.title);
    expect(document.documentElement).toHaveAttribute("lang", "en");
  });

  it("switches texts and the lang attribute, and remembers the choice", async () => {
    renderApp();

    await userEvent.selectOptions(screen.getByLabelText(en.language.label), "fi");

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(fi.dashboard.title);
    expect(screen.getByRole("link", { name: fi.nav.items.orders })).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("lang", "fi");
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("fi");
  });

  it("does not store a language before the user chooses one", () => {
    renderApp();
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBeNull();
  });

  it("keeps <html lang> in sync when the language is set programmatically", async () => {
    await setLanguage("fi");
    expect(document.documentElement).toHaveAttribute("lang", "fi");
  });

  it("uses the same storage key as the inline script in index.html", () => {
    expect(indexHtml).toContain(`"${LANGUAGE_STORAGE_KEY}"`);
  });
});
