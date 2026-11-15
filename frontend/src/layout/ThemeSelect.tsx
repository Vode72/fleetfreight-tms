import { useTranslation } from "react-i18next";

import { useTheme, type Theme } from "../theme/theme";
import { PreferenceSelect } from "./PreferenceSelect";

export function ThemeSelect() {
  const { t } = useTranslation();
  const { theme, setTheme } = useTheme();
  const options: { value: Theme; label: string }[] = [
    { value: "business-light", label: t("theme.businessLight") },
    { value: "control-dark", label: t("theme.controlDark") },
  ];

  return <PreferenceSelect label={t("theme.label")} value={theme} options={options} onChange={setTheme} />;
}
