import { useTranslation } from "react-i18next";

/** Neutral full-screen view while the session check runs, so the login page never flashes. */
export function AuthLoading() {
  const { t } = useTranslation();

  return (
    <div className="auth-screen">
      <p role="status" className="muted">
        {t("auth.loading")}
      </p>
    </div>
  );
}
