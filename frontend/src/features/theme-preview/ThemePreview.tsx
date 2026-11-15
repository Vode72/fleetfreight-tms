import type { ParseKeys } from "i18next";
import { useTranslation } from "react-i18next";

import "./theme-preview.css";

interface Sample {
  tone: string;
  labelKey: ParseKeys;
}

const STATUSES: readonly Sample[] = [
  { tone: "status-planned", labelKey: "preview.statuses.planned" },
  { tone: "status-confirmed", labelKey: "preview.statuses.confirmed" },
  { tone: "status-in-progress", labelKey: "preview.statuses.inProgress" },
  { tone: "status-delivered", labelKey: "preview.statuses.delivered" },
  { tone: "status-invoiced", labelKey: "preview.statuses.invoiced" },
  { tone: "status-cancelled", labelKey: "preview.statuses.cancelled" },
];

const SEVERITIES: readonly Sample[] = [
  { tone: "severity-red", labelKey: "preview.severities.red" },
  { tone: "severity-orange", labelKey: "preview.severities.orange" },
  { tone: "severity-yellow", labelKey: "preview.severities.yellow" },
];

const BADGES: readonly Sample[] = [
  { tone: "badge-adr", labelKey: "preview.badgeNames.adr" },
  { tone: "badge-gdp", labelKey: "preview.badgeNames.gdp" },
  { tone: "badge-thermo", labelKey: "preview.badgeNames.thermo" },
];

/** Static illustrative widths, not domain data. */
const CAPACITY: readonly { level: "ok" | "warn" | "over"; labelKey: ParseKeys; width: string }[] = [
  { level: "ok", labelKey: "preview.capacityLevels.ok", width: "45%" },
  { level: "warn", labelKey: "preview.capacityLevels.warn", width: "88%" },
  { level: "over", labelKey: "preview.capacityLevels.over", width: "100%" },
];

function ChipGroup({ title, samples }: { title: string; samples: readonly Sample[] }) {
  const { t } = useTranslation();

  return (
    <section className="panel" aria-label={title}>
      <h2>{title}</h2>
      <ul className="chip-list">
        {samples.map((sample) => (
          <li key={sample.tone} className="chip" data-tone={sample.tone}>
            {t(sample.labelKey)}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Shows the semantic tokens in the active theme, so both themes can be checked at a glance. */
export function ThemePreview() {
  const { t } = useTranslation();

  return (
    <div className="preview-grid">
      <ChipGroup title={t("preview.status")} samples={STATUSES} />
      <ChipGroup title={t("preview.severity")} samples={SEVERITIES} />
      <ChipGroup title={t("preview.badges")} samples={BADGES} />
      <section className="panel" aria-label={t("preview.capacity")}>
        <h2>{t("preview.capacity")}</h2>
        <ul className="capacity-list">
          {CAPACITY.map((row) => (
            <li key={row.level} className="capacity-row">
              <span className="capacity-label">{t(row.labelKey)}</span>
              <span className="capacity-track" aria-hidden="true">
                <span className="capacity-fill" data-level={row.level} style={{ width: row.width }} />
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
