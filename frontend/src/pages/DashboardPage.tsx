import { useTranslation } from "react-i18next";

import { HealthStatus } from "../features/health/HealthStatus";
import { ThemePreview } from "../features/theme-preview/ThemePreview";
import { Tabs } from "../layout/Tabs";

export function DashboardPage() {
  const { t } = useTranslation();

  return (
    <>
      <h1 className="page-title">{t("dashboard.title")}</h1>
      <Tabs
        label={t("dashboard.tabsLabel")}
        tabs={[
          {
            id: "overview",
            label: t("dashboard.tabs.overview"),
            panel: (
              <div className="panel">
                <HealthStatus />
              </div>
            ),
          },
          { id: "theme-preview", label: t("dashboard.tabs.themePreview"), panel: <ThemePreview /> },
        ]}
      />
    </>
  );
}
