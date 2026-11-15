import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./en.json";
import fi from "./fi.json";

export const SUPPORTED_LANGUAGES = ["en", "fi"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];
export const DEFAULT_LANGUAGE: Language = "en";

/** Switches the UI language at runtime. The selector UI arrives in 1C. */
export function setLanguage(language: Language): Promise<unknown> {
  return i18n.changeLanguage(language);
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, fi: { translation: fi } },
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: SUPPORTED_LANGUAGES,
  interpolation: { escapeValue: false },
});

export default i18n;
