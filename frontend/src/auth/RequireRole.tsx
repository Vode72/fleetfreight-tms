import type { ReactNode } from "react";

import { hasRole, type Role } from "./roles";
import { useAuth } from "./useAuth";

interface RequireRoleProps {
  roles: readonly Role[];
  children: ReactNode;
  /** Shown instead of the children when the role does not match. Default: nothing. */
  fallback?: ReactNode;
}

/**
 * Renders the children only for the given roles. UI convenience only: the server enforces
 * permissions, so never rely on this alone (see roles.ts).
 */
export function RequireRole({ roles, children, fallback = null }: RequireRoleProps) {
  const { user } = useAuth();
  return hasRole(user, roles) ? children : fallback;
}
