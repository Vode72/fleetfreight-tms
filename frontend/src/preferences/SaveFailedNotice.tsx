import { useTranslation } from "react-i18next";

import { dismissSaveFailed, useSaveFailed } from "./saveNotice";

export function SaveFailedNotice() {
  const { t } = useTranslation();
  const visible = useSaveFailed();
  if (!visible) return null;

  return (
    <div role="status" className="save-notice">
      <span>{t("preferences.saveFailed")}</span>
      <button type="button" onClick={dismissSaveFailed}>
        {t("preferences.dismiss")}
      </button>
    </div>
  );
}
