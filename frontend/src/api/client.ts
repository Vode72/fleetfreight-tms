import createClient from "openapi-fetch";

import type { paths } from "./schema";

/**
 * Typed API client built from the generated OpenAPI types.
 * Calls go to the relative `/api` prefix: the Vite dev server proxies it to the backend
 * (see vite.config.ts), so no backend address is hard-coded here.
 * `fetch` is resolved on every call so tests can replace `globalThis.fetch`.
 */
export function createApiClient() {
  return createClient<paths>({
    baseUrl: new URL("/api", window.location.origin).href,
    fetch: (request) => globalThis.fetch(request),
  });
}

export const api = createApiClient();
