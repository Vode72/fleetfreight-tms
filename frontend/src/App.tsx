import { useTranslation } from "react-i18next";

import { HealthStatus } from "./features/health/HealthStatus";

export function App() {
  const { t } = useTranslation();

  return (
    <main className="app-main">
      <h1 className="app-title">{t("app.name")}</h1>
      <HealthStatus />
    </main>
  );
}
