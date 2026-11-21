/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// The frontend never hard-codes the backend address. It calls relative `/api/...` URLs.
// In development Vite forwards them to the backend and strips the `/api` prefix, so the
// browser only talks to one origin and no CORS configuration is needed.
// Override the target with BACKEND_URL (read here, in Node, not exposed to the browser).
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [
    react(),
    // D88: precache only the app's own files. No runtime caching: API and sign-in requests
    // (`/api/...`) always go to the network, so no business or session data is stored on the
    // device. A new version waits for the user ("prompt"), never reloads mid-task.
    VitePWA({
      registerType: "prompt",
      injectRegister: false,
      manifest: false, // public/manifest.webmanifest is linked from index.html
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,webmanifest}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
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
    alias: {
      // The plugin's virtual module exists only in a Vite build; tests use a stub.
      "virtual:pwa-register": fileURLToPath(new URL("./src/test/pwaRegisterStub.ts", import.meta.url)),
    },
  },
});
