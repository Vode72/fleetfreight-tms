import { describe, expect, it, vi } from "vitest";

import { CSRF_HEADER_NAME, CSRF_HEADER_VALUE, createApiClient } from "./client";
import { onUnauthorized } from "./unauthorized";
import { empty, json, mockBackend } from "../test/mockBackend";

describe("api client", () => {
  it("sends the CSRF header on POST but not on GET", async () => {
    const backend = mockBackend();
    const api = createApiClient();

    await api.GET("/health");
    await api.POST("/auth/logout");

    expect(backend.callsTo("GET", "/health")[0]?.headers.has(CSRF_HEADER_NAME)).toBe(false);
    expect(backend.callsTo("POST", "/auth/logout")[0]?.headers.get(CSRF_HEADER_NAME)).toBe(CSRF_HEADER_VALUE);
    expect(CSRF_HEADER_VALUE).toBe("fleetfreight");
  });

  it("publishes 401 answers, except for the login attempt itself", async () => {
    const backend = mockBackend({ user: null });
    backend.routes["POST /auth/login"] = () => empty(401);
    const listener = vi.fn();
    const off = onUnauthorized(listener);
    const api = createApiClient();

    await api.POST("/auth/login", { body: { email: "a@demo.example.com", password: "x" } });
    expect(listener).not.toHaveBeenCalled();

    await api.GET("/auth/me");
    expect(listener).toHaveBeenCalledTimes(1);
    off();
  });

  it("does not publish other errors", async () => {
    const backend = mockBackend();
    backend.routes["GET /health"] = () => json({ status: "error", database: "error" }, 503);
    const listener = vi.fn();
    const off = onUnauthorized(listener);

    await createApiClient().GET("/health");
    expect(listener).not.toHaveBeenCalled();
    off();
  });
});
