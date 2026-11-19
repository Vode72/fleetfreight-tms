import { useCallback, useState } from "react";

import { readStored, writeStored } from "../lib/safeStorage";

export const SIDEBAR_STORAGE_KEY = "ff.sidebar";

/**
 * Collapsed state of the sidebar, remembered in the browser.
 * Without a remembered choice the sidebar starts collapsed on narrow screens (tablet, D81).
 */
export function useSidebarCollapsed(narrow = false): { collapsed: boolean; toggle: () => void } {
  const [stored, setStored] = useState(() => readStored(SIDEBAR_STORAGE_KEY));
  const collapsed = stored === null ? narrow : stored === "collapsed";

  const toggle = useCallback(() => {
    const next = collapsed ? "expanded" : "collapsed";
    writeStored(SIDEBAR_STORAGE_KEY, next);
    setStored(next);
  }, [collapsed]);

  return { collapsed, toggle };
}
