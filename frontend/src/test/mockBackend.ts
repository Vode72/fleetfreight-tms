import { vi } from "vitest";

import type { AuthUser } from "../auth/roles";

/** Demo accounts used in tests (invented data, `*.example.com`). */
export const USERS = {
  admin: { id: "00000000-0000-4000-8000-000000000001", email: "admin@demo.example.com", role: "admin" },
  planner: { id: "00000000-0000-4000-8000-000000000002", email: "planner@demo.example.com", role: "planner" },
  viewer: { id: "00000000-0000-4000-8000-000000000003", email: "viewer@demo.example.com", role: "viewer" },
} as const satisfies Record<string, AuthUser>;

export interface RecordedCall {
  method: string;
  /** Path below the `/api` prefix, with the query string. */
  path: string;
  headers: Headers;
  body: string;
}

type Handler = (call: RecordedCall) => Response | Promise<Response>;

export interface MockBackend {
  calls: RecordedCall[];
  /** Calls to one endpoint, e.g. `callsTo("POST", "/auth/login")`. */
  callsTo: (method: string, path: string) => RecordedCall[];
  /** The session the fake server currently has (null: signed out). Setting it null mimics expiry. */
  user: AuthUser | null;
  /** Replace or add a handler, e.g. `backend.routes["GET /health"] = ...`. */
  routes: Record<string, Handler>;
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function empty(status: number, headers: Record<string, string> = {}): Response {
  return new Response(null, { status, headers });
}

/**
 * Replaces `fetch` with a fake backend that keeps one session. It records every request so tests
 * can check methods and headers. Unknown routes answer 404 so a missing handler shows up clearly.
 */
export function mockBackend(
  options: { user?: AuthUser | null; loginAs?: AuthUser } = {},
): MockBackend {
  const backend: MockBackend = {
    calls: [],
    callsTo: (method, path) => backend.calls.filter((c) => c.method === method && c.path === path),
    user: options.user === undefined ? USERS.admin : options.user,
    routes: {},
  };

  backend.routes = {
    "GET /auth/me": () => (backend.user ? json(backend.user) : empty(401)),
    "POST /auth/login": () => {
      backend.user = options.loginAs ?? USERS.planner;
      return empty(204);
    },
    "POST /auth/logout": () => {
      if (!backend.user) return empty(401);
      backend.user = null;
      return empty(204);
    },
    "GET /health": () => json({ status: "ok", database: "ok" }),
  };

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request) => {
      const url = new URL(input.url);
      const call: RecordedCall = {
        method: input.method,
        path: `${url.pathname.replace(/^\/api/, "")}${url.search}`,
        headers: new Headers(input.headers),
        body: await input.clone().text(),
      };
      backend.calls.push(call);
      const handler = backend.routes[`${call.method} ${url.pathname.replace(/^\/api/, "")}`];
      return handler ? handler(call) : empty(404);
    }),
  );

  return backend;
}
