import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import en from "../../i18n/en.json";
import { HealthStatus } from "./HealthStatus";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HealthStatus", () => {
  it("shows loading first, then ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ status: "ok", database: "ok" }, 200)));
    render(<HealthStatus />);

    expect(screen.getByRole("status")).toHaveTextContent(en.health.loading);
    expect(await screen.findByText(en.health.ok)).toHaveAttribute("data-state", "ok");
  });

  it("shows database down on 503", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ status: "error", database: "error" }, 503)),
    );
    render(<HealthStatus />);

    expect(await screen.findByText(en.health.databaseDown)).toHaveAttribute("data-state", "database-down");
  });

  it("shows unreachable when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<HealthStatus />);

    expect(await screen.findByText(en.health.unreachable)).toHaveAttribute("data-state", "unreachable");
  });

  it("shows unreachable on an unexpected server error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Bad gateway", { status: 502 })));
    render(<HealthStatus />);

    expect(await screen.findByText(en.health.unreachable)).toBeInTheDocument();
  });
});
