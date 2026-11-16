import { patchPreferences, type PreferencesUpdate } from "./preferencesApi";
import { clearFailedFields, markFailedFields, markSavedFields } from "./saveNotice";

type Field = keyof PreferencesUpdate;

/**
 * Serialises preference saves: one PATCH in flight at a time, and changes made meanwhile are
 * merged so only the latest value of each field is sent. This keeps the server value equal to
 * the last choice even when the user switches quickly.
 */
let pending: PreferencesUpdate = {};
let inFlight: Promise<void> | null = null;

async function flush(): Promise<void> {
  while (Object.keys(pending).length > 0) {
    const body = pending;
    pending = {};
    const fields = Object.keys(body) as Field[];
    const result = await patchPreferences(body);
    if (result === "saved") markSavedFields(fields);
    else if (result === "failed") markFailedFields(fields);
    else clearFailedFields();
  }
}

export function enqueueSave(update: PreferencesUpdate): Promise<void> {
  pending = { ...pending, ...update };
  inFlight ??= flush().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

/** Test helper: resolves when no save is pending or in flight. */
export async function waitForSaves(): Promise<void> {
  while (inFlight) await inFlight;
}

/** Test helper. */
export function resetSaveQueue(): void {
  pending = {};
  inFlight = null;
}
