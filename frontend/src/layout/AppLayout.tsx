import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Outlet } from "react-router";

import { SaveFailedNotice } from "../preferences/SaveFailedNotice";
import "./layout.css";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { PHONE_QUERY, TABLET_QUERY, useMediaQuery } from "./useMediaQuery";
import { useSidebarCollapsed } from "./useSidebarCollapsed";

/**
 * App shell (D81): desktop shows the sidebar, a tablet starts with it collapsed to icons,
 * and a phone opens it as a drawer from the menu button in the top bar.
 */
export function AppLayout() {
  const { t } = useTranslation();
  const isPhone = useMediaQuery(PHONE_QUERY);
  const isTablet = useMediaQuery(TABLET_QUERY);
  const { collapsed, toggle } = useSidebarCollapsed(isTablet);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const drawerOpen = isPhone && menuOpen;

  const closeMenu = useCallback((returnFocus: boolean) => {
    setMenuOpen(false);
    if (returnFocus) menuButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeMenu(true);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => { document.removeEventListener("keydown", onKeyDown); };
  }, [drawerOpen, closeMenu]);

  const layout = isPhone ? "phone" : "wide";

  return (
    <div
      className="app-shell"
      data-layout={layout}
      data-sidebar={!isPhone && collapsed ? "collapsed" : "expanded"}
      data-menu={drawerOpen ? "open" : "closed"}
    >
      <a className="skip-link" href="#main">
        {t("layout.skipToContent")}
      </a>
      <TopBar
        compact={isPhone}
        menuOpen={drawerOpen}
        menuButtonRef={menuButtonRef}
        onMenuToggle={() => { setMenuOpen((open) => !open); }}
      />
      <Sidebar
        collapsed={!isPhone && collapsed}
        onToggle={toggle}
        mode={isPhone ? "drawer" : "rail"}
        open={drawerOpen}
        onNavigate={() => { closeMenu(false); }}
      />
      {drawerOpen && (
        <button
          type="button"
          className="drawer-backdrop"
          aria-label={t("nav.closeMenu")}
          tabIndex={-1}
          onClick={() => { closeMenu(true); }}
        />
      )}
      <main id="main" className="app-main" tabIndex={-1} inert={drawerOpen}>
        <Outlet />
      </main>
      <SaveFailedNotice />
    </div>
  );
}
