import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import en from "../i18n/en.json";
import { renderApp } from "../test/renderApp";
import { PHONE_QUERY, TABLET_QUERY } from "./useMediaQuery";
import { SIDEBAR_STORAGE_KEY } from "./useSidebarCollapsed";

/** Fakes the viewport: which of the shell's media queries match. */
function setViewport(width: "phone" | "tablet" | "desktop") {
  const matching = new Set<string>(
    width === "phone"
      ? [PHONE_QUERY, TABLET_QUERY]
      : width === "tablet"
        ? [TABLET_QUERY]
        : [],
  );
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: matching.has(query),
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }));
}

describe("responsive shell (D81)", () => {
  it("desktop: sidebar expanded, settings and user in the top bar, no menu button", async () => {
    setViewport("desktop");
    await renderApp();

    expect(
      screen.queryByRole("button", { name: en.nav.openMenu }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: en.nav.toggle })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(
      within(screen.getByRole("banner")).getByRole("button", {
        name: en.auth.logout,
      }),
    ).toBeInTheDocument();
  });

  it("tablet: sidebar starts collapsed to icons, links keep their names", async () => {
    setViewport("tablet");
    await renderApp();

    expect(screen.getByRole("button", { name: en.nav.toggle })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(
      screen.getByRole("link", { name: en.nav.items.orders }),
    ).toBeInTheDocument();
  });

  it("tablet: a remembered choice wins over the default", async () => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, "expanded");
    setViewport("tablet");
    await renderApp();

    expect(screen.getByRole("button", { name: en.nav.toggle })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("phone: menu is closed at start, the top bar has only the menu button and title", async () => {
    setViewport("phone");
    await renderApp();

    const menuButton = screen.getByRole("button", { name: en.nav.openMenu });
    expect(menuButton).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByRole("navigation", { name: en.nav.label }),
    ).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("banner")).queryByRole("combobox"),
    ).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("banner")).queryByRole("button", {
        name: en.auth.logout,
      }),
    ).not.toBeInTheDocument();
  });

  it("phone: opening the menu shows navigation, settings and sign-out; choosing a link closes it", async () => {
    setViewport("phone");
    await renderApp();

    await userEvent.click(
      screen.getByRole("button", { name: en.nav.openMenu }),
    );

    const nav = screen.getByRole("navigation", { name: en.nav.label });
    expect(
      screen.getByRole("button", { name: en.nav.closeMenu, expanded: true }),
    ).toBeInTheDocument();
    expect(
      within(nav).getByRole("combobox", { name: en.theme.label }),
    ).toBeInTheDocument();
    expect(
      within(nav).getByRole("combobox", { name: en.language.label }),
    ).toBeInTheDocument();
    expect(
      within(nav).getByRole("button", { name: en.auth.logout }),
    ).toBeInTheDocument();
    expect(
      within(nav).queryByRole("button", { name: en.nav.toggle }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("main", { hidden: true })).toHaveAttribute("inert");

    await userEvent.click(
      within(nav).getByRole("link", { name: en.nav.items.trips }),
    );

    expect(
      screen.queryByRole("navigation", { name: en.nav.label }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      en.nav.items.trips,
    );
    expect(screen.getByRole("main")).not.toHaveAttribute("inert");
  });

  it("phone: Escape closes the menu and returns focus to the menu button", async () => {
    setViewport("phone");
    await renderApp();

    await userEvent.click(
      screen.getByRole("button", { name: en.nav.openMenu }),
    );
    await userEvent.keyboard("{Escape}");

    const menuButton = screen.getByRole("button", { name: en.nav.openMenu });
    expect(menuButton).toHaveAttribute("aria-expanded", "false");
    expect(menuButton).toHaveFocus();
    expect(
      screen.queryByRole("navigation", { name: en.nav.label }),
    ).not.toBeInTheDocument();
  });

  it("phone: the backdrop closes the menu", async () => {
    setViewport("phone");
    await renderApp();

    await userEvent.click(
      screen.getByRole("button", { name: en.nav.openMenu }),
    );
    const backdrop =
      document.querySelector<HTMLButtonElement>(".drawer-backdrop");
    expect(backdrop).not.toBeNull();
    if (backdrop) await userEvent.click(backdrop);

    expect(
      screen.queryByRole("navigation", { name: en.nav.label }),
    ).not.toBeInTheDocument();
  });
});
