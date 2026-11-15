import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import en from "../i18n/en.json";
import { renderApp } from "../test/renderApp";
import { SIDEBAR_STORAGE_KEY } from "./useSidebarCollapsed";

describe("navigation", () => {
  it("renders landmarks and the three sections with their links", () => {
    renderApp();

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: en.nav.label });

    const expected: Record<string, string[]> = {
      [en.nav.sections.loadPlanning]: [en.nav.items.orders, en.nav.items.trips, en.nav.items.customers],
      [en.nav.sections.trafficPlanning]: [
        en.nav.items.board,
        en.nav.items.jobWorkspace,
        en.nav.items.fleetTimeline,
        en.nav.items.routeRisk,
      ],
      [en.nav.sections.administration]: [en.nav.items.fleetPartners, en.nav.items.pricing, en.nav.items.settings],
    };
    for (const [section, links] of Object.entries(expected)) {
      const region = within(nav).getByRole("region", { name: section });
      expect(within(region).getAllByRole("link").map((l) => l.textContent)).toEqual(links);
    }
  });

  it("marks the current page with aria-current and shows its placeholder", () => {
    renderApp("/trips");

    expect(screen.getByRole("link", { name: en.nav.items.trips })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: en.nav.items.orders })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: en.nav.dashboard })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(en.nav.items.trips);
    expect(screen.getByText(en.placeholder.description)).toBeInTheDocument();
  });

  it("navigates with the keyboard", async () => {
    renderApp();

    screen.getByRole("link", { name: en.nav.items.pricing }).focus();
    await userEvent.keyboard("{Enter}");

    expect(screen.getByRole("link", { name: en.nav.items.pricing })).toHaveAttribute("aria-current", "page");
  });

  it("shows a not-found view for unknown paths", () => {
    renderApp("/nope");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(en.notFound.title);
  });

  it("collapses the sidebar, keeps link names, and remembers the choice", async () => {
    renderApp();

    const toggle = screen.getByRole("button", { name: en.nav.toggle });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(toggle);

    expect(screen.getByRole("button", { name: en.nav.toggle })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("link", { name: en.nav.items.orders })).toBeInTheDocument();
    expect(localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe("collapsed");
  });
});

describe("dashboard tabs", () => {
  it("shows the health status and moves between tabs with the arrow keys", async () => {
    renderApp();

    expect(screen.getByRole("tab", { name: en.dashboard.tabs.overview })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("region", { name: en.health.title })).toBeInTheDocument();

    screen.getByRole("tab", { name: en.dashboard.tabs.overview }).focus();
    await userEvent.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: en.dashboard.tabs.themePreview })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("region", { name: en.preview.capacity })).toBeInTheDocument();
  });

  it("wraps with ArrowLeft and ArrowRight and supports Home and End", async () => {
    renderApp();
    const overview = screen.getByRole("tab", { name: en.dashboard.tabs.overview });
    const preview = screen.getByRole("tab", { name: en.dashboard.tabs.themePreview });

    overview.focus();
    await userEvent.keyboard("{ArrowLeft}");
    expect(preview).toHaveAttribute("aria-selected", "true");
    expect(preview).toHaveFocus();

    await userEvent.keyboard("{ArrowRight}");
    expect(overview).toHaveAttribute("aria-selected", "true");

    await userEvent.keyboard("{End}");
    expect(preview).toHaveAttribute("aria-selected", "true");
    expect(preview).toHaveFocus();

    await userEvent.keyboard("{Home}");
    expect(overview).toHaveAttribute("aria-selected", "true");
    expect(overview).toHaveFocus();
  });

  it("makes the tab panel focusable", () => {
    renderApp();
    expect(screen.getByRole("tabpanel")).toHaveAttribute("tabindex", "0");
  });
});
