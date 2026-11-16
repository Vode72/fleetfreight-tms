import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { LANGUAGE_STORAGE_KEY, setLanguage } from "../i18n";
import en from "../i18n/en.json";
import fi from "../i18n/fi.json";
import { empty, mockBackend, USERS } from "../test/mockBackend";
import { renderApp } from "../test/renderApp";
import { THEME_STORAGE_KEY, initTheme } from "../theme/theme";
import { clearFailedFields } from "./saveNotice";
import { resetSaveQueue, waitForSaves } from "./saveQueue";

async function signIn() {
  await userEvent.type(screen.getByLabelText(en.auth.login.email), USERS.planner.email);
  await userEvent.type(screen.getByLabelText(en.auth.login.password), "demo-password");
  await userEvent.click(screen.getByRole("button", { name: en.auth.login.submit }));
}

describe("server-side preferences (D49)", () => {
  afterEach(() => {
    resetSaveQueue();
    clearFailedFields();
  });

  it("adopts the saved theme and language on page load and refreshes the local cache", async () => {
    const backend = mockBackend({ user: { ...USERS.planner, theme: "control-dark", language: "fi" } });
    await renderApp("/", { backend });

    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    expect(document.documentElement).toHaveAttribute("lang", "fi");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("control-dark");
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("fi");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(fi.dashboard.title);
  });

  it("adopts the saved preferences after login", async () => {
    const backend = mockBackend({
      user: null,
      loginAs: { ...USERS.planner, theme: "control-dark", language: "fi" },
    });
    await renderApp("/login", { backend });
    await signIn();

    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    });
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("fi");
  });

  it("keeps the local choice when the server has null", async () => {
    localStorage.setItem(THEME_STORAGE_KEY, "control-dark");
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "fi");
    initTheme();
    await setLanguage("fi");

    await renderApp("/", { backend: mockBackend({ user: { ...USERS.planner, theme: null, language: null } }) });

    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    expect(document.documentElement).toHaveAttribute("lang", "fi");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("control-dark");
  });

  it("ignores unknown server values", async () => {
    initTheme();
    await renderApp("/", { backend: mockBackend({ user: { ...USERS.planner, theme: "neon", language: "sv" } }) });
    expect(document.documentElement).toHaveAttribute("data-theme", "business-light");
    expect(document.documentElement).toHaveAttribute("lang", "en");
  });

  it("changing the theme sends PATCH with only the theme, with the CSRF header", async () => {
    const backend = mockBackend({ user: USERS.planner });
    await renderApp("/", { backend });

    await userEvent.selectOptions(screen.getByLabelText(en.theme.label), "control-dark");

    await waitFor(() => {
      expect(backend.callsTo("PATCH", "/auth/me/preferences")).toHaveLength(1);
    });
    const call = backend.callsTo("PATCH", "/auth/me/preferences")[0];
    expect(JSON.parse(call?.body ?? "")).toEqual({ theme: "control-dark" });
    expect(call?.headers.get("X-Requested-With")).toBe("fleetfreight");
    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
  });

  it("changing the language sends PATCH with only the language", async () => {
    const backend = mockBackend({ user: USERS.planner });
    await renderApp("/", { backend });

    await userEvent.selectOptions(screen.getByLabelText(en.language.label), "fi");

    await waitFor(() => {
      expect(backend.callsTo("PATCH", "/auth/me/preferences")).toHaveLength(1);
    });
    expect(JSON.parse(backend.callsTo("PATCH", "/auth/me/preferences")[0]?.body ?? "")).toEqual({ language: "fi" });
  });

  it("a failed save shows a notice in the current language and keeps the choice", async () => {
    const backend = mockBackend({ user: USERS.planner });
    backend.routes["PATCH /auth/me/preferences"] = () => empty(500);
    await renderApp("/", { backend });

    await userEvent.selectOptions(screen.getByLabelText(en.theme.label), "control-dark");

    expect(await screen.findByText(en.preferences.saveFailed)).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    expect(screen.getByLabelText(en.theme.label)).toHaveValue("control-dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("control-dark");

    await userEvent.click(screen.getByRole("button", { name: en.preferences.dismiss }));
    expect(screen.queryByText(en.preferences.saveFailed)).not.toBeInTheDocument();
  });

  it("a network error also shows the notice", async () => {
    const backend = mockBackend({ user: USERS.planner });
    backend.routes["PATCH /auth/me/preferences"] = () => {
      throw new TypeError("network");
    };
    await renderApp("/", { backend });

    await userEvent.selectOptions(screen.getByLabelText(en.language.label), "fi");

    expect(await screen.findByText(fi.preferences.saveFailed)).toBeInTheDocument();
  });

  it("the login page uses only local storage (no PATCH)", async () => {
    const backend = mockBackend({ user: null });
    await renderApp("/login", { backend });

    await userEvent.selectOptions(screen.getByLabelText(en.theme.label), "control-dark");

    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("control-dark");
    expect(backend.callsTo("PATCH", "/auth/me/preferences")).toHaveLength(0);
  });

  it("logging out keeps the local choice", async () => {
    const backend = mockBackend({ user: { ...USERS.planner, theme: "control-dark", language: null } });
    await renderApp("/", { backend });

    await userEvent.click(screen.getByRole("button", { name: en.auth.logout }));

    await screen.findByLabelText(en.auth.login.email);
    expect(document.documentElement).toHaveAttribute("data-theme", "control-dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("control-dark");
  });
  it("quick switches send one request at a time and the server ends with the last choice", async () => {
    const backend = mockBackend({ user: USERS.planner });
    const original = backend.routes["PATCH /auth/me/preferences"];
    if (!original) throw new Error("missing PATCH handler");
    const release: (() => void)[] = [];
    let concurrent = 0;
    let maxConcurrent = 0;
    backend.routes["PATCH /auth/me/preferences"] = async (call) => {
      concurrent += 1;
      maxConcurrent = Math.max(maxConcurrent, concurrent);
      await new Promise<void>((resolve) => release.push(resolve));
      concurrent -= 1;
      return original(call);
    };
    await renderApp("/", { backend });

    const select = screen.getByLabelText(en.theme.label);
    await userEvent.selectOptions(select, "control-dark");
    await userEvent.selectOptions(select, "business-light");
    await userEvent.selectOptions(select, "control-dark");

    while (release.length > 0 || backend.callsTo("PATCH", "/auth/me/preferences").length < 2) {
      await waitFor(() => {
        expect(release.length).toBeGreaterThan(0);
      });
      release.shift()?.();
    }
    await waitForSaves();

    const bodies = backend.callsTo("PATCH", "/auth/me/preferences").map((c) => JSON.parse(c.body) as unknown);
    expect(maxConcurrent).toBe(1);
    expect(bodies).toEqual([{ theme: "control-dark" }, { theme: "control-dark" }]);
    expect(backend.user?.theme).toBe("control-dark");
  });

  it("the notice stays while another field is still unsaved", async () => {
    const backend = mockBackend({ user: USERS.planner });
    const original = backend.routes["PATCH /auth/me/preferences"];
    if (!original) throw new Error("missing PATCH handler");
    backend.routes["PATCH /auth/me/preferences"] = (call) =>
      "theme" in (JSON.parse(call.body) as object) ? empty(500) : original(call);
    await renderApp("/", { backend });

    await userEvent.selectOptions(screen.getByLabelText(en.theme.label), "control-dark");
    expect(await screen.findByText(en.preferences.saveFailed)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(en.language.label), "fi");
    await waitForSaves();
    expect(screen.getByText(fi.preferences.saveFailed)).toBeInTheDocument();
  });

  it("a save that ends in 401 (session ended) shows no notice", async () => {
    const backend = mockBackend({ user: USERS.planner });
    backend.routes["PATCH /auth/me/preferences"] = () => empty(401);
    await renderApp("/", { backend });

    await userEvent.selectOptions(screen.getByLabelText(en.theme.label), "control-dark");
    await waitForSaves();

    expect(screen.queryByText(en.preferences.saveFailed)).not.toBeInTheDocument();
  });
});
