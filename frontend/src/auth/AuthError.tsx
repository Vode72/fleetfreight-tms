import { useTranslation } from "react-i18next";

import { useAuth } from "./useAuth";

/** The session check itself failed (backend down or unexpected answer). Offers a retry. */
export function AuthError() {
  const { t } = useTranslation();
  const { retry } = useAuth();

  return (
    <div className="auth-screen">
      <section className="panel auth-card" aria-labelledby="auth-error-title">
        <h1 id="auth-error-title" className="page-title">
          {t("auth.sessionError.title")}
        </h1>
        <p role="alert" className="auth-alert">
          {t("auth.sessionError.message")}
        </p>
        <button type="button" onClick={retry}>
          {t("auth.sessionError.retry")}
        </button>
      </section>
    </div>
  );
}
