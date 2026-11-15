import createClient from "openapi-fetch";

import type { paths } from "./schema";
import { notifyUnauthorized } from "./unauthorized";

/** CSRF protection: the backend rejects state-changing requests without this header (403). */
export const CSRF_HEADER_NAME = "X-Requested-With";
export const CSRF_HEADER_VALUE = "fleetfreight";

const SAFE_METHODS: ReadonlySet<string> = new Set(["GET", "HEAD", "OPTIONS"]);

/**
 * Typed API client built from the generated OpenAPI types.
 * Calls go to the relative `/api` prefix: the Vite dev server proxies it to the backend
 * (see vite.config.ts), so no backend address is hard-coded here.
 * `fetch` is resolved on every call so tests can replace `globalThis.fetch`.
 *
 * Two cross-cutting concerns live in the middleware so no caller can forget them:
 *  - every POST/PUT/PATCH/DELETE carries the CSRF header;
 *  - any 401 (except the login attempt itself, where it means "wrong credentials")
 *    is published through `onUnauthorized`, so an expired session sends the user to the login page.
 */
export function createApiClient() {
  const client = createClient<paths>({
    baseUrl: new URL("/api", window.location.origin).href,
    fetch: (request) => globalThis.fetch(request),
  });

  client.use({
    onRequest({ request }) {
      if (!SAFE_METHODS.has(request.method.toUpperCase())) {
        request.headers.set(CSRF_HEADER_NAME, CSRF_HEADER_VALUE);
      }
      return request;
    },
    onResponse({ response, schemaPath }) {
      if (response.status === 401 && schemaPath !== "/auth/login") notifyUnauthorized();
    },
  });

  return client;
}

export const api = createApiClient();
