import { useCallback, useEffect, useState } from "react";

/** Chromium's install event (Chrome, Edge, Opera); not in the DOM typings. */
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export type InstallState =
  /** Running as an installed app: nothing to show. */
  | "installed"
  /** The browser offers its install prompt (Chromium browsers): show the button. */
  | "available"
  /** No install prompt (e.g. Firefox, Safari): show how to install from the browser menu. */
  | "manual";

function isStandalone(): boolean {
  if (typeof window.matchMedia !== "function") return false;
  return window.matchMedia("(display-mode: standalone)").matches;
}

/**
 * Install support by browser (D88). The button appears only when the browser fires
 * `beforeinstallprompt`, so no browser shows a button that does nothing.
 */
export function useInstallPrompt(): { state: InstallState; install: () => Promise<void> } {
  const [event, setEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState(isStandalone);

  useEffect(() => {
    function onPrompt(e: Event) {
      e.preventDefault(); // show our own button instead of the browser's mini bar
      setEvent(e as BeforeInstallPromptEvent);
    }
    function onInstalled() {
      setInstalled(true);
      setEvent(null);
    }
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const install = useCallback(async () => {
    if (!event) return;
    await event.prompt();
    await event.userChoice;
    setEvent(null); // a prompt can be used only once
  }, [event]);

  const state: InstallState = installed ? "installed" : event ? "available" : "manual";
  return { state, install };
}
