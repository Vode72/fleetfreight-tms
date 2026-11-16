import { useSyncExternalStore } from "react";

/** Tiny store for the non-blocking "could not save" notice. */
let visible = false;
const listeners = new Set<() => void>();

function emit(): void {
  listeners.forEach((listener) => {
    listener();
  });
}

export function showSaveFailed(): void {
  visible = true;
  emit();
}

export function dismissSaveFailed(): void {
  visible = false;
  emit();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useSaveFailed(): boolean {
  return useSyncExternalStore(subscribe, () => visible);
}
