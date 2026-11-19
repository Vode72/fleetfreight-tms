import { useCallback, useSyncExternalStore } from "react";

/** Breakpoints of the app shell (D81). Keep in sync with layout.css. */
export const PHONE_QUERY = "(max-width: 640px)";
export const TABLET_QUERY = "(max-width: 1024px)";

function getMediaQueryList(query: string): MediaQueryList | null {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return null;
  return window.matchMedia(query);
}

/** Whether a CSS media query currently matches. False where matchMedia is unavailable. */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = getMediaQueryList(query);
      if (!list) return () => undefined;
      list.addEventListener("change", onChange);
      return () => { list.removeEventListener("change", onChange); };
    },
    [query],
  );
  const getSnapshot = () => getMediaQueryList(query)?.matches ?? false;

  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
