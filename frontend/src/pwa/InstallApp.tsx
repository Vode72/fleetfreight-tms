import { useTranslation } from "react-i18next";

import { useInstallPrompt } from "./useInstallPrompt";

/**
 * Install button where the browser supports it (Chrome, Edge, Opera); elsewhere (Firefox,
 * Safari) a short hint to use the browser's own menu. Nothing once installed (D88).
 */
export function InstallApp() {
  const { t } = useTranslation();
  const { state, install } = useInstallPrompt();

  if (state === "installed") return null;
  if (state === "available") {
    return (
      <button
        type="button"
        className="pwa-install"
        onClick={() => {
          void install();
        }}
      >
        {t("pwa.install")}
      </button>
    );
  }
  return <p className="pwa-install-help">{t("pwa.installHelp")}</p>;
}
