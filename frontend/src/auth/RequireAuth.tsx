import { Navigate, Outlet, useLocation } from "react-router";

import { AuthError } from "./AuthError";
import { AuthLoading } from "./AuthLoading";
import { loginUrlFor, LOGIN_PATH } from "./safeReturnPath";
import { useAuth } from "./useAuth";

/** Layout route: everything below it needs a signed-in user. */
export function RequireAuth() {
  const { state } = useAuth();
  const location = useLocation();

  switch (state.status) {
    case "loading":
      return <AuthLoading />;
    case "error":
      return <AuthError />;
    case "unauthenticated":
      // After an explicit sign-out start from a clean login page; otherwise remember the path.
      return <Navigate to={state.reason === "loggedOut" ? LOGIN_PATH : loginUrlFor(location)} replace />;
    case "authenticated":
      return <Outlet />;
  }
}
