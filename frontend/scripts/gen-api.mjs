// Generates src/api/schema.ts from the backend OpenAPI description.
// Source comes from OPENAPI_URL (default: local backend on port 8000). It may be an http(s) URL
// or a path to an OpenAPI JSON file (relative paths are resolved from the current directory).
// Runs the CLI with the current Node binary (no shell), so it works the same on Windows, macOS and Linux.
import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = fileURLToPath(new URL("..", import.meta.url));
// The package does not export its CLI path, so locate it in node_modules directly.
const cli = join(frontendDir, "node_modules", "openapi-typescript", "bin", "cli.js");
const source = process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json";
const url = /^https?:\/\//.test(source) ? source : resolve(process.cwd(), source);

const result = spawnSync(process.execPath, [cli, url, "-o", "src/api/schema.ts"], {
  cwd: frontendDir,
  stdio: "inherit",
});
process.exit(result.status ?? 1);
