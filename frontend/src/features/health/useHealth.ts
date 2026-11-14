import { useCallback, useEffect, useState } from "react";

import { api } from "../../api/client";

/** Abort the health check if the backend does not answer within this time. */
const HEALTH_TIMEOUT_MS = 5000;

export type HealthState = "loading" | "ok" | "database-down" | "unreachable";

/** Fetches the backend health once on mount; `refresh` repeats the check. */
export function useHealth(): { state: HealthState; refresh: () => void } {
  const [state, setState] = useState<HealthState>("loading");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(HEALTH_TIMEOUT_MS)]);

    api
      .GET("/health", { signal })
      .then(({ data, error }) => {
        if (controller.signal.aborted) return;
        if (data?.database === "ok" && data.status === "ok") setState("ok");
        else if (error?.database === "error") setState("database-down");
        else setState("unreachable");
      })
      .catch(() => {
        if (!controller.signal.aborted) setState("unreachable");
      });

    return () => {
      controller.abort();
    };
  }, [attempt]);

  const refresh = useCallback(() => {
    setState("loading");
    setAttempt((n) => n + 1);
  }, []);

  return { state, refresh };
}
