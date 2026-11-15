import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuth } from "../auth/useAuth";

/** Signed-in user (email and role) plus the sign-out button. */
export function UserMenu() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!user) return null;

  async function handleLogout() {
    setBusy(true);
    setFailed(false);
    const signedOut = await logout();
    if (!signedOut) {
      setBusy(false);
      setFailed(true);
    }
  }

  return (
    <div className="topbar-user" role="group" aria-label={t("auth.user.label")}>
      <span className="topbar-user-email">{user.email}</span>
      <span className="topbar-user-role">{t(`auth.roles.${user.role}`)}</span>
      {failed && (
        <span role="alert" className="topbar-user-error">
          {t("auth.logoutFailed")}
        </span>
      )}
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          void handleLogout();
        }}
      >
        {t("auth.logout")}
      </button>
    </div>
  );
}
