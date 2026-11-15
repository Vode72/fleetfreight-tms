import { useTranslation } from "react-i18next";
import { Navigate, useSearchParams } from "react-router";

import { AuthError } from "../auth/AuthError";
import { AuthLoading } from "../auth/AuthLoading";
import { RETURN_PARAM, safeReturnPath } from "../auth/safeReturnPath";
import { useAuth } from "../auth/useAuth";
import { LoginForm } from "../features/auth/LoginForm";
import "../features/auth/auth.css";
import { LanguageSelect } from "../layout/LanguageSelect";
import "../layout/layout.css";
import { ThemeSelect } from "../layout/ThemeSelect";

/** Public route. Theme and language pickers stay available here. */
export function LoginPage() {
  const { t } = useTranslation();
  const { state } = useAuth();
  const [params] = useSearchParams();

  if (state.status === "loading") return <AuthLoading />;
  if (state.status === "error") return <AuthError />;
  if (state.status === "authenticated") return <Navigate to={safeReturnPath(params.get(RETURN_PARAM))} replace />;

  const notice =
    state.reason === "expired" ? t("auth.notices.expired") : state.reason === "loggedOut" ? t("auth.notices.loggedOut") : null;

  return (
    <div className="login-shell">
      <header className="topbar">
        <span className="topbar-title">{t("app.name")}</span>
        <div className="topbar-settings" role="group" aria-label={t("layout.settings")}>
          <ThemeSelect />
          <LanguageSelect />
        </div>
      </header>
      <main className="login-main">
        <section className="panel auth-card" aria-labelledby="login-title">
          <h1 id="login-title" className="page-title">
            {t("auth.login.title")}
          </h1>
          {notice && (
            <p role="status" className="auth-notice">
              {notice}
            </p>
          )}
          <LoginForm />
        </section>
      </main>
    </div>
  );
}
