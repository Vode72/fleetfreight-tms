import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import { startServiceWorker } from "./pwa/serviceWorker";
import "./i18n";
import { initTheme } from "./theme/theme";
import "./theme/tokens.css";
import "./styles.css";

// Set the remembered theme before the first render so the page never flashes the wrong one.
initTheme();

// Service worker only in production builds (D88); in development it would cache stale code.
if (import.meta.env.PROD) startServiceWorker();

const container = document.getElementById("root");
if (!container) throw new Error("Root element #root not found");

createRoot(container).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
