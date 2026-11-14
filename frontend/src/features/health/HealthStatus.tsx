import { useTranslation } from "react-i18next";

import { useHealth, type HealthState } from "./useHealth";

const MESSAGE_KEYS: Record<HealthState, string> = {
  loading: "health.loading",
  ok: "health.ok",
  "database-down": "health.databaseDown",
  unreachable: "health.unreachable",
};

export function HealthStatus() {
  const { t } = useTranslation();
  const { state, refresh } = useHealth();

  return (
    <section aria-label={t("health.title")}>
      <h2>{t("health.title")}</h2>
      <p className="health-status" data-state={state} role="status">
        {t(MESSAGE_KEYS[state])}
      </p>
      {state !== "loading" && (
        <button type="button" onClick={refresh}>
          {t("health.retry")}
        </button>
      )}
    </section>
  );
}
