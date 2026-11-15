import { useTranslation } from "react-i18next";
import { Link } from "react-router";

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <>
      <h1 className="page-title">{t("notFound.title")}</h1>
      <section className="panel">
        <p className="muted">{t("notFound.description")}</p>
        <p>
          <Link to="/">{t("notFound.back")}</Link>
        </p>
      </section>
    </>
  );
}
