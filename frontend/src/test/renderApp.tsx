import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";

import { App } from "../App";
import en from "../i18n/en.json";
import { mockBackend, type MockBackend } from "./mockBackend";

function LocationProbe() {
  const { pathname, search } = useLocation();
  return <output data-testid="location">{`${pathname}${search}`}</output>;
}

/** Path and query the router is currently at. */
export function currentLocation(): string {
  return screen.getByTestId("location").textContent;
}

/**
 * Renders the whole app against a fake backend (signed in as admin unless told otherwise)
 * and waits until the startup session check has finished.
 */
export async function renderApp(path = "/", options: { backend?: MockBackend; waitForSession?: boolean } = {}) {
  const backend = options.backend ?? mockBackend();
  const result = render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <LocationProbe />
    </MemoryRouter>,
  );
  if (options.waitForSession ?? true) {
    await waitFor(() => {
      expect(screen.queryByText(en.auth.loading)).not.toBeInTheDocument();
    });
    // Let the redirect that follows the session check finish.
    await act(async () => {
      await Promise.resolve();
    });
  }
  return { ...result, backend };
}
