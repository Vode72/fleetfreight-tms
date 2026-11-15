import { useTranslation } from "react-i18next";

import { isLanguage, setLanguage, type Language } from "../i18n";
import { PreferenceSelect } from "./PreferenceSelect";

export function LanguageSelect() {
  const { t, i18n } = useTranslation();
  const language: Language = isLanguage(i18n.language) ? i18n.language : "en";
  const options: { value: Language; label: string }[] = [
    { value: "en", label: t("language.en") },
    { value: "fi", label: t("language.fi") },
  ];

  return (
    <PreferenceSelect
      label={t("language.label")}
      value={language}
      options={options}
      onChange={(next) => {
        void setLanguage(next);
      }}
    />
  );
}
