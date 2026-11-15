import { api } from "../api/client";
import type { AuthUser } from "./roles";

export type MeResult = { kind: "user"; user: AuthUser } | { kind: "unauthenticated" } | { kind: "error" };

export type LoginResult =
  | { ok: true }
  | { ok: false; reason: "invalid" | "validation" | "network" | "unexpected" }
  | { ok: false; reason: "rateLimited"; retryAfterSeconds: number | null };

/** Who is signed in? 401 is an ordinary answer ("nobody"), anything else unexpected is an error. */
export async function fetchMe(signal?: AbortSignal): Promise<MeResult> {
  try {
    const { data, response } = await api.GET("/auth/me", { signal });
    if (data) return { kind: "user", user: data };
    if (response.status === 401) return { kind: "unauthenticated" };
    return { kind: "error" };
  } catch {
    return { kind: "error" };
  }
}

/** Retry-After is delay-seconds ("120"); an HTTP-date or garbage gives null. */
export function parseRetryAfter(value: string | null): number | null {
  if (value === null || !/^\d{1,9}$/.test(value.trim())) return null;
  return Number(value.trim());
}

/** Posts the credentials. The password is sent as typed and never stored anywhere. */
export async function postLogin(email: string, password: string): Promise<LoginResult> {
  try {
    const { response } = await api.POST("/auth/login", { body: { email, password } });
    if (response.status === 204) return { ok: true };
    if (response.status === 401) return { ok: false, reason: "invalid" };
    if (response.status === 422) return { ok: false, reason: "validation" };
    if (response.status === 429) {
      return { ok: false, reason: "rateLimited", retryAfterSeconds: parseRetryAfter(response.headers.get("Retry-After")) };
    }
    return { ok: false, reason: "unexpected" };
  } catch {
    return { ok: false, reason: "network" };
  }
}

/** True when the user is signed out afterwards. A stale session (401) already counts as signed out. */
export async function postLogout(): Promise<boolean> {
  try {
    const { response } = await api.POST("/auth/logout");
    return response.status === 204 || response.status === 401;
  } catch {
    return false;
  }
}
