/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The frontend never hard-codes the backend address. It calls relative `/api/...` URLs.
// In development Vite forwards them to the backend and strips the `/api` prefix, so the
// browser only talks to one origin and no CORS configuration is needed.
// Override the target with BACKEND_URL (read here, in Node, not exposed to the browser).
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: backendUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    // Process CSS so tests can read the token files as raw text (contrast and colour-lint tests).
    css: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
