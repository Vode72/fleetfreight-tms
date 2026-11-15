import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";

import { Icon } from "./Icon";
import { DASHBOARD_ITEM, NAV_SECTIONS, type NavItem } from "./navigation";

function SidebarLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const { t } = useTranslation();
  const label = t(item.labelKey);

  return (
    <NavLink to={item.path} end={item.path === "/"} className="sidebar-link" title={collapsed ? label : undefined}>
      <Icon name={item.icon} />
      <span className={collapsed ? "visually-hidden" : "sidebar-link-label"}>{label}</span>
    </NavLink>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { t } = useTranslation();

  return (
    <nav id="sidebar" className="sidebar" aria-label={t("nav.label")}>
      <ul className="sidebar-list">
        <li>
          <SidebarLink item={DASHBOARD_ITEM} collapsed={collapsed} />
        </li>
      </ul>
      {NAV_SECTIONS.map((section) => (
        <section key={section.id} className="sidebar-section" aria-labelledby={`nav-${section.id}`}>
          <h2 id={`nav-${section.id}`} className={collapsed ? "visually-hidden" : "sidebar-heading"}>
            {t(section.labelKey)}
          </h2>
          <ul className="sidebar-list">
            {section.items.map((item) => (
              <li key={item.path}>
                <SidebarLink item={item} collapsed={collapsed} />
              </li>
            ))}
          </ul>
        </section>
      ))}
      <button
        type="button"
        className="sidebar-toggle"
        aria-expanded={!collapsed}
        aria-controls="sidebar"
        onClick={onToggle}
      >
        <Icon name={collapsed ? "chevronRight" : "chevronLeft"} />
        <span className={collapsed ? "visually-hidden" : undefined}>
          {collapsed ? t("nav.expand") : t("nav.collapse")}
        </span>
      </button>
    </nav>
  );
}
