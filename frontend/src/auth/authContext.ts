import { createContext } from "react";

import type { LoginResult } from "./authApi";
import type { AuthUser } from "./roles";

export type AuthState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "authenticated"; user: AuthUser }
  /** `reason` tells the login page whether to explain why the user is here. */
  | { status: "unauthenticated"; reason: "initial" | "expired" | "loggedOut" };

export interface AuthContextValue {
  state: AuthState;
  /** The signed-in user, or null in every other state. */
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<LoginResult>;
  /** Resolves true when the user is signed out afterwards. */
  logout: () => Promise<boolean>;
  /** Repeats the startup session check (after a network error). */
  retry: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
