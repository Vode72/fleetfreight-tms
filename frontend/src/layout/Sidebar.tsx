import type { Ref } from "react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";

import { hasRole } from "../auth/roles";
import { useAuth } from "../auth/useAuth";
import { Icon } from "./Icon";
import { LanguageSelect } from "./LanguageSelect";
import { DASHBOARD_ITEM, NAV_SECTIONS, type NavItem } from "./navigation";
import { ThemeSelect } from "./ThemeSelect";
import { UserMenu } from "./UserMenu";

interface SidebarLinkProps {
  item: NavItem;
  collapsed: boolean;
  onNavigate?: () => void;
}

function SidebarLink({ item, collapsed, onNavigate }: SidebarLinkProps) {
  const { t } = useTranslation();
  const label = t(item.labelKey);

  return (
    <NavLink
      to={item.path}
      end={item.path === "/"}
      className="sidebar-link"
      title={collapsed ? label : undefined}
      onClick={onNavigate}
    >
      <Icon name={item.icon} />
      <span className={collapsed ? "visually-hidden" : "sidebar-link-label"}>{label}</span>
    </NavLink>
  );
}

interface SidebarProps {
  ref?: Ref<HTMLElement>;
  collapsed: boolean;
  onToggle: () => void;
  /** "rail": fixed column (desktop, tablet). "drawer": slides in over the content (phone, D81). */
  mode?: "rail" | "drawer";
  /** Drawer only: whether it is shown. */
  open?: boolean;
  /** Called after a link is chosen; closes the drawer on a phone. */
  onNavigate?: () => void;
}

export function Sidebar({ ref, collapsed, onToggle, mode = "rail", open = false, onNavigate }: SidebarProps) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const drawer = mode === "drawer";

  return (
    <nav
      ref={ref}
      id="sidebar"
      className="sidebar"
      aria-label={t("nav.label")}
      data-mode={mode}
      hidden={drawer && !open ? true : undefined}
    >
      <ul className="sidebar-list">
        <li>
          <SidebarLink item={DASHBOARD_ITEM} collapsed={collapsed} onNavigate={onNavigate} />
        </li>
      </ul>
      {NAV_SECTIONS.filter((section) => hasRole(user, section.roles)).map((section) => (
        <section key={section.id} className="sidebar-section" aria-labelledby={`nav-${section.id}`}>
          <h2 id={`nav-${section.id}`} className={collapsed ? "visually-hidden" : "sidebar-heading"}>
            {t(section.labelKey)}
          </h2>
          <ul className="sidebar-list">
            {section.items.map((item) => (
              <li key={item.path}>
                <SidebarLink item={item} collapsed={collapsed} onNavigate={onNavigate} />
              </li>
            ))}
          </ul>
        </section>
      ))}
      {drawer ? (
        <div className="sidebar-account">
          <div className="sidebar-settings" role="group" aria-label={t("layout.settings")}>
            <ThemeSelect />
            <LanguageSelect />
          </div>
          <UserMenu />
        </div>
      ) : (
        <button
          type="button"
          className="sidebar-toggle"
          aria-expanded={!collapsed}
          aria-controls="sidebar"
          onClick={onToggle}
        >
          <Icon name={collapsed ? "chevronRight" : "chevronLeft"} />
          <span className={collapsed ? "visually-hidden" : undefined}>{t("nav.toggle")}</span>
        </button>
      )}
    </nav>
  );
}
