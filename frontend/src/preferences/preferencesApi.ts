import type { components } from "../api/schema";
import { api } from "../api/client";

export type PreferencesUpdate = components["schemas"]["PreferencesUpdate"];

/** Saves the signed-in user's theme and/or language. True when the server accepted it. */
export async function patchPreferences(body: PreferencesUpdate): Promise<boolean> {
  try {
    const { data } = await api.PATCH("/auth/me/preferences", { body });
    return data !== undefined;
  } catch {
    return false;
  }
}
