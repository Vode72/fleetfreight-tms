import { useCallback, useState } from "react";

import { readStored, writeStored } from "../lib/safeStorage";

export const SIDEBAR_STORAGE_KEY = "ff.sidebar";

/** Collapsed state of the sidebar, remembered in the browser. */
export function useSidebarCollapsed(): { collapsed: boolean; toggle: () => void } {
  const [collapsed, setCollapsed] = useState(() => readStored(SIDEBAR_STORAGE_KEY) === "collapsed");

  const toggle = useCallback(() => {
    setCollapsed((previous) => {
      writeStored(SIDEBAR_STORAGE_KEY, previous ? "expanded" : "collapsed");
      return !previous;
    });
  }, []);

  return { collapsed, toggle };
}
