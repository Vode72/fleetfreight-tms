import { useSyncExternalStore } from "react";

/**
 * Tiny store for the non-blocking "could not save" notice. Failures are tracked per field, so a
 * successful save of one field does not hide the notice while another field is still unsaved.
 */
const failed = new Set<string>();
let visible = false;
const listeners = new Set<() => void>();

function emit(): void {
  visible = failed.size > 0;
  listeners.forEach((listener) => {
    listener();
  });
}

export function markFailedFields(fields: readonly string[]): void {
  fields.forEach((field) => failed.add(field));
  emit();
}

export function markSavedFields(fields: readonly string[]): void {
  fields.forEach((field) => failed.delete(field));
  emit();
}

/** Hides the notice (user dismissed it, or the session ended). */
export function clearFailedFields(): void {
  failed.clear();
  emit();
}

export const dismissSaveFailed = clearFailedFields;

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useSaveFailed(): boolean {
  return useSyncExternalStore(subscribe, () => visible);
}
