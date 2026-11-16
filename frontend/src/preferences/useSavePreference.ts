import { useCallback } from "react";

import { useAuth } from "../auth/useAuth";
import { patchPreferences, type PreferencesUpdate } from "./preferencesApi";
import { dismissSaveFailed, showSaveFailed } from "./saveNotice";

/**
 * Returns a function that saves a preference in the background for the signed-in user.
 * Without a session (login page) it does nothing: the local cache is the only store.
 * A failed save keeps the choice in this browser and shows a notice.
 */
export function useSavePreference(): (update: PreferencesUpdate) => void {
  const { user } = useAuth();
  const signedIn = user !== null;

  return useCallback(
    (update) => {
      if (!signedIn) return;
      void patchPreferences(update).then((saved) => {
        if (saved) dismissSaveFailed();
        else showSaveFailed();
      });
    },
    [signedIn],
  );
}
