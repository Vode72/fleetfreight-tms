import { useEffect, useState } from "react";
import { registerSW } from "virtual:pwa-register";

type Listener = () => void;
let needRefresh = false;
let update: ((reload?: boolean) => Promise<void>) | null = null;
const listeners = new Set<Listener>();

/**
 * Registers the service worker once (D88). It precaches only the app's own files; API and
 * sign-in responses always go to the network. A new version waits until the user chooses to
 * reload, so nothing is lost mid-task.
 */
export function startServiceWorker(): void {
  if (update || !("serviceWorker" in navigator)) return;
  update = registerSW({
    onNeedRefresh() {
      needRefresh = true;
      listeners.forEach((listener) => {
        listener();
      });
    },
  });
}

/** Whether a new version is waiting, and how to take it into use. */
export function useServiceWorkerUpdate(): { needRefresh: boolean; reload: () => void } {
  const [, setTick] = useState(0);
  useEffect(() => {
    const listener = () => {
      setTick((n) => n + 1);
    };
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);
  return {
    needRefresh,
    reload: () => {
      void update?.(true);
    },
  };
}
