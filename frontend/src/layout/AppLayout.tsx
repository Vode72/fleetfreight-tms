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
  const [wasPhone, setWasPhone] = useState(isPhone);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const drawerOpen = isPhone && menuOpen;

  // Leaving the phone layout closes the drawer, so it does not reopen on its own later.
  if (wasPhone !== isPhone) {
    setWasPhone(isPhone);
    if (!isPhone) setMenuOpen(false);
  }

  const closeMenu = useCallback((focusTarget: "menuButton" | "main") => {
    setMenuOpen(false);
    // The drawer is hidden after this render; move focus somewhere that stays visible.
    queueMicrotask(() => {
      (focusTarget === "main" ? mainRef.current : menuButtonRef.current)?.focus();
    });
  }, []);

  // Opening the drawer moves focus to its first link.
  useEffect(() => {
    if (drawerOpen) sidebarRef.current?.querySelector<HTMLElement>("a")?.focus();
  }, [drawerOpen]);

  useEffect(() => {
    if (!drawerOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeMenu("menuButton");
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
        ref={sidebarRef}
        collapsed={!isPhone && collapsed}
        onToggle={toggle}
        mode={isPhone ? "drawer" : "rail"}
        open={drawerOpen}
        onNavigate={() => { closeMenu("main"); }}
      />
      {drawerOpen && (
        <button
          type="button"
          className="drawer-backdrop"
          aria-label={t("nav.closeMenu")}
          tabIndex={-1}
          onClick={() => { closeMenu("menuButton"); }}
        />
      )}
      <main ref={mainRef} id="main" className="app-main" tabIndex={-1} inert={drawerOpen}>
        <Outlet />
      </main>
      <SaveFailedNotice />
    </div>
  );
}
