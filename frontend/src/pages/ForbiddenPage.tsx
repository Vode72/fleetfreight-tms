import { useTranslation } from "react-i18next";
import { Link } from "react-router";

/** Shown when a signed-in user opens a view their role does not include (UI courtesy; the server enforces). */
export function ForbiddenPage() {
  const { t } = useTranslation();

  return (
    <>
      <h1 className="page-title">{t("forbidden.title")}</h1>
      <section className="panel">
        <p className="muted">{t("forbidden.description")}</p>
        <p>
          <Link to="/">{t("notFound.back")}</Link>
        </p>
      </section>
    </>
  );
}
