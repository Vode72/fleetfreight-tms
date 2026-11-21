import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";

import { useServiceWorkerUpdate } from "./serviceWorker";
import { useOnlineStatus } from "./useOnlineStatus";
import "./pwa.css";

/**
 * Connection banner and the new-version prompt, shown on every page (D88). The live region
 * stays in the page so screen readers announce what appears in it. "Later" hides the prompt
 * until the user moves to another page.
 */
export function PwaNotices() {
  const { t } = useTranslation();
  const online = useOnlineStatus();
  const { needRefresh, reload } = useServiceWorkerUpdate();
  const { pathname } = useLocation();
  const [laterOn, setLaterOn] = useState<string | null>(null);
  const showUpdate = needRefresh && laterOn !== pathname;

  return (
    <div className="pwa-notices" role="status" aria-live="polite">
      {!online && <p className="pwa-notice pwa-notice-offline">{t("pwa.offline")}</p>}
      {showUpdate && (
        <div className="pwa-notice pwa-notice-update">
          <span>{t("pwa.updateAvailable")}</span>
          <button type="button" onClick={reload}>
            {t("pwa.reload")}
          </button>
          <button
            type="button"
            onClick={() => {
              setLaterOn(pathname);
            }}
          >
            {t("pwa.later")}
          </button>
        </div>
      )}
    </div>
  );
}
