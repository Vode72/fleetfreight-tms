import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { LanguageSelect } from "./LanguageSelect";
import { ThemeSelect } from "./ThemeSelect";

export function TopBar() {
  const { t } = useTranslation();

  return (
    <header className="topbar">
      <Link to="/" className="topbar-title">
        {t("app.name")}
      </Link>
      <div className="topbar-settings" role="group" aria-label={t("layout.settings")}>
        <ThemeSelect />
        <LanguageSelect />
      </div>
    </header>
  );
}
