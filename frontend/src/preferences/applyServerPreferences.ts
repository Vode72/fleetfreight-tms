import { isLanguage, setLanguage } from "../i18n";
import { isTheme, setTheme } from "../theme/theme";
import type { AuthUser } from "../auth/roles";

/**
 * Adopts the preferences saved on the server (D49). setTheme/setLanguage also refresh the
 * localStorage cache that theme-init.js reads, so the next load does not flash.
 * null (or an unknown value) means "no saved choice": the local choice stays.
 */
export function applyServerPreferences(user: Pick<AuthUser, "theme" | "language">): void {
  if (user.theme != null && isTheme(user.theme)) setTheme(user.theme);
  if (user.language != null && isLanguage(user.language)) void setLanguage(user.language);
}
