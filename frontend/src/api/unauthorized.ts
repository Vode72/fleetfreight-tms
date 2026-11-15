/**
 * Tiny publish/subscribe channel for "the server says the session is gone" (HTTP 401).
 * The API client publishes, the auth provider subscribes. This keeps the client free of any
 * React or router dependency while making 401 handling central: no view has to check for it.
 */
type Listener = () => void;

const listeners = new Set<Listener>();

export function onUnauthorized(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function notifyUnauthorized(): void {
  listeners.forEach((listener) => {
    listener();
  });
}
