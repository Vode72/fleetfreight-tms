import type { components } from "../api/schema";

export type Role = components["schemas"]["Role"];
export type AuthUser = components["schemas"]["MeResponse"];

/**
 * Role helpers for the UI.
 *
 * IMPORTANT: the server enforces every permission (`require_role` on each endpoint). Hiding a
 * link or a section here is only a convenience so people do not see things they cannot use.
 * It is not a security boundary and must never be the only check for anything.
 */
export function hasRole(user: AuthUser | null | undefined, allowed: readonly Role[] | undefined): boolean {
  if (!user) return false;
  if (allowed === undefined) return true; // no restriction: any signed-in user
  return allowed.includes(user.role);
}
