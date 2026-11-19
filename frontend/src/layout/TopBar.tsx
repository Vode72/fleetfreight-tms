import type { RefObject } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Icon } from "./Icon";
import { LanguageSelect } from "./LanguageSelect";
import { ThemeSelect } from "./ThemeSelect";
import { UserMenu } from "./UserMenu";

interface TopBarProps {
  /** Phone layout: menu button and title only; settings and user move into the drawer. */
  compact?: boolean;
  menuOpen?: boolean;
  menuButtonRef?: RefObject<HTMLButtonElement | null>;
  onMenuToggle?: () => void;
}

export function TopBar({ compact = false, menuOpen = false, menuButtonRef, onMenuToggle }: TopBarProps) {
  const { t } = useTranslation();

  return (
    <header className="topbar">
      <div className="topbar-left">
        {compact && (
          <button
            ref={menuButtonRef}
            type="button"
            className="topbar-menu-button"
            aria-expanded={menuOpen}
            aria-controls="sidebar"
            onClick={onMenuToggle}
          >
            <Icon name={menuOpen ? "close" : "menu"} />
            <span className="visually-hidden">{t(menuOpen ? "nav.closeMenu" : "nav.openMenu")}</span>
          </button>
        )}
        <Link to="/" className="topbar-title">
          {t("app.name")}
        </Link>
      </div>
      {!compact && (
        <div className="topbar-right">
          <div className="topbar-settings" role="group" aria-label={t("layout.settings")}>
            <ThemeSelect />
            <LanguageSelect />
          </div>
          <UserMenu />
        </div>
      )}
    </header>
  );
}
