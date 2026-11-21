import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useServiceWorkerUpdate } from "./serviceWorker";
import { useOnlineStatus } from "./useOnlineStatus";
import "./pwa.css";

/** Connection banner and the new-version prompt, shown on every page (D88). */
export function PwaNotices() {
  const { t } = useTranslation();
  const online = useOnlineStatus();
  const { needRefresh, reload } = useServiceWorkerUpdate();
  const [later, setLater] = useState(false);

  return (
    <div className="pwa-notices">
      {!online && (
        <p role="status" className="pwa-notice pwa-notice-offline">
          {t("pwa.offline")}
        </p>
      )}
      {needRefresh && !later && (
        <div role="status" className="pwa-notice pwa-notice-update">
          <span>{t("pwa.updateAvailable")}</span>
          <button type="button" onClick={reload}>
            {t("pwa.reload")}
          </button>
          <button
            type="button"
            onClick={() => {
              setLater(true);
            }}
          >
            {t("pwa.later")}
          </button>
        </div>
      )}
    </div>
  );
}
