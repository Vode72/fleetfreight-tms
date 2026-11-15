import type { ParseKeys } from "i18next";
import { useTranslation } from "react-i18next";

export function PlaceholderPage({ titleKey }: { titleKey: ParseKeys }) {
  const { t } = useTranslation();

  return (
    <>
      <h1 className="page-title">{t(titleKey)}</h1>
      <section className="panel" aria-label={t("placeholder.title")}>
        <h2>{t("placeholder.title")}</h2>
        <p className="muted">{t("placeholder.description")}</p>
      </section>
    </>
  );
}
