import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { setLanguage } from "../i18n";
import { DEFAULT_THEME, setTheme } from "../theme/theme";

afterEach(async () => {
  cleanup();
  // Reset the remembered preferences so tests stay independent.
  await setLanguage("en");
  setTheme(DEFAULT_THEME);
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});
