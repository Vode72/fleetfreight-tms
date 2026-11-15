import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { readStored, writeStored } from "../lib/safeStorage";
import en from "./en.json";
import fi from "./fi.json";

export const SUPPORTED_LANGUAGES = ["en", "fi"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];
export const DEFAULT_LANGUAGE: Language = "en";
export const LANGUAGE_STORAGE_KEY = "ff.language";

export function isLanguage(value: string | null | undefined): value is Language {
  return SUPPORTED_LANGUAGES.some((language) => language === value);
}

function readStoredLanguage(): Language {
  const stored = readStored(LANGUAGE_STORAGE_KEY);
  return isLanguage(stored) ? stored : DEFAULT_LANGUAGE;
}

/** Switches the UI language at runtime. The choice is remembered and mirrored to <html lang>. */
export function setLanguage(language: Language): Promise<unknown> {
  return i18n.changeLanguage(language);
}

i18n.on("languageChanged", (language) => {
  document.documentElement.lang = language;
  if (isLanguage(language)) writeStored(LANGUAGE_STORAGE_KEY, language);
});

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, fi: { translation: fi } },
  lng: readStoredLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  supportedLngs: SUPPORTED_LANGUAGES,
  interpolation: { escapeValue: false },
  initAsync: false,
});

export default i18n;
