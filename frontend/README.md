# FleetFreight TMS frontend

React + TypeScript (strict) + Vite. Tests with Vitest and Testing Library, linting with ESLint (flat config).
Requires Node 22.

## Start

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

The page shows the backend health status, so start the backend too (port 8000, see `../backend/README.md`).

The browser only calls relative `/api/...` URLs. The Vite dev server forwards them to the backend and
strips the `/api` prefix (`/api/health` -> `GET /health`), so no backend address is hard-coded and
CORS is not needed in development. To use another backend: `BACKEND_URL=http://host:port npm run dev`
(PowerShell: `$env:BACKEND_URL="http://host:port"; npm run dev`).
A production deployment must route `/api` to the backend the same way (reverse proxy).

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | dev server with the `/api` proxy |
| `npm run build` | typecheck and production build to `dist/` |
| `npm run preview` | serve the production build locally |
| `npm run typecheck` | `tsc` in strict mode |
| `npm run lint` | ESLint |
| `npm test` | Vitest (single run) |
| `npm run gen:api` | regenerate `src/api/schema.ts` from the backend OpenAPI description |

## API types

`src/api/schema.ts` is generated and committed. Never edit it by hand and never write API types manually.
With the backend running:

```bash
npm run gen:api
# another source:
OPENAPI_URL=http://host:port/openapi.json npm run gen:api
# PowerShell: $env:OPENAPI_URL="http://host:port/openapi.json"; npm run gen:api
```

Commit the regenerated file together with the backend change that caused it. If an endpoint you need is
missing from the schema, it has to be added to the backend first.

## Translations

UI texts live in `src/i18n/en.json` and `src/i18n/fi.json` (default language: English). Every new text goes
into both files; a test fails if their keys differ. Switch language in code with `setLanguage("fi")`.

## Styling

Components use only CSS variables from `src/theme/`. Currently placeholders; the real themes
(Business Light, Control Dark) come in the next PR.

## Dependencies

- **TypeScript is pinned to `~5.9`.** `openapi-typescript` 7.x declares `typescript: ^5.x` as a peer dependency.
  Remove the pin when `openapi-typescript` supports a newer TypeScript major version.
- **Known dev-only advisory:** `npm audit` reports a moderate `minimatch` issue through `typescript-eslint`.
  It affects development tooling only, not the built app. `npm audit fix --force` would downgrade
  `typescript-eslint`, so it is left as is until an upstream fix is released.
