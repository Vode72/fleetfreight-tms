import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { applyServerPreferences } from "../preferences/applyServerPreferences";
import { onUnauthorized } from "../api/unauthorized";
import { fetchMe, postLogin, postLogout, type LoginResult } from "./authApi";
import { AuthContext, type AuthContextValue, type AuthState } from "./authContext";

/**
 * Holds the session state. The session itself is an httpOnly cookie that the browser sends
 * by itself; the frontend never reads or stores a token. On start it asks `GET /auth/me`.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void fetchMe(controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      if (result.kind === "user") {
        applyServerPreferences(result.user);
        setState({ status: "authenticated", user: result.user });
      } else if (result.kind === "unauthenticated") setState({ status: "unauthenticated", reason: "initial" });
      else setState({ status: "error" });
    });
    return () => {
      controller.abort();
    };
  }, [attempt]);

  // A 401 from any later request means the session expired or was revoked: reset the state.
  // The route guard then redirects to the login page.
  useEffect(
    () =>
      onUnauthorized(() => {
        setState((previous) =>
          previous.status === "authenticated" ? { status: "unauthenticated", reason: "expired" } : previous,
        );
      }),
    [],
  );

  const login = useCallback(async (email: string, password: string): Promise<LoginResult> => {
    const result = await postLogin(email, password);
    if (!result.ok) return result;
    const me = await fetchMe();
    if (me.kind !== "user") return { ok: false, reason: me.kind === "error" ? "network" : "unexpected" };
    applyServerPreferences(me.user);
    setState({ status: "authenticated", user: me.user });
    return { ok: true };
  }, []);

  const logout = useCallback(async (): Promise<boolean> => {
    const signedOut = await postLogout();
    if (signedOut) setState({ status: "unauthenticated", reason: "loggedOut" });
    return signedOut;
  }, []);

  const retry = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ state, user: state.status === "authenticated" ? state.user : null, login, logout, retry }),
    [state, login, logout, retry],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
