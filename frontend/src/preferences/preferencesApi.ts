import type { components } from "../api/schema";
import { api } from "../api/client";

export type PreferencesUpdate = components["schemas"]["PreferencesUpdate"];

/** "unauthorized": the session ended (e.g. logged out mid-request); not shown as a save failure. */
export type SaveResult = "saved" | "failed" | "unauthorized";

/** Saves the signed-in user's theme and/or language. Never throws. */
export async function patchPreferences(body: PreferencesUpdate): Promise<SaveResult> {
  try {
    const { data, response } = await api.PATCH("/auth/me/preferences", { body });
    if (response.status === 401) return "unauthorized";
    return data !== undefined ? "saved" : "failed";
  } catch {
    return "failed";
  }
}
