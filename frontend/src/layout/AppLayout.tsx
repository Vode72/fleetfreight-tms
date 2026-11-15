import { useTranslation } from "react-i18next";
import { Outlet } from "react-router";

import "./layout.css";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { useSidebarCollapsed } from "./useSidebarCollapsed";

export function AppLayout() {
  const { t } = useTranslation();
  const { collapsed, toggle } = useSidebarCollapsed();

  return (
    <div className="app-shell" data-sidebar={collapsed ? "collapsed" : "expanded"}>
      <a className="skip-link" href="#main">
        {t("layout.skipToContent")}
      </a>
      <TopBar />
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <main id="main" className="app-main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
