import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { api, CSRF_HEADER_NAME } from "../api/client";
import en from "../i18n/en.json";
import fi from "../i18n/fi.json";
import { empty, json, mockBackend, USERS } from "../test/mockBackend";
import { currentLocation, renderApp } from "../test/renderApp";

async function signIn(email = USERS.planner.email, password = "demo-password") {
  await userEvent.type(screen.getByLabelText(en.auth.login.email), email);
  await userEvent.type(screen.getByLabelText(en.auth.login.password), password);
  await userEvent.click(screen.getByRole("button", { name: en.auth.login.submit }));
}

describe("startup", () => {
  it("shows a neutral loading view, then the app when signed in", async () => {
    const backend = mockBackend({ user: USERS.planner });
    const { findByRole } = await renderApp("/trips", { backend });

    expect(await findByRole("heading", { level: 1, name: en.nav.items.trips })).toBeInTheDocument();
    expect(backend.callsTo("GET", "/auth/me")).toHaveLength(1);
    expect(currentLocation()).toBe("/trips");
  });

  it("does not show the login form while the session check is running", async () => {
    const backend = mockBackend({ user: null });
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const original = backend.routes["GET /auth/me"];
    backend.routes["GET /auth/me"] = async (call) => {
      await gate;
      return original ? original(call) : empty(500);
    };

    await renderApp("/orders", { backend, waitForSession: false });

    expect(screen.getByText(en.auth.loading)).toBeInTheDocument();
    expect(screen.queryByLabelText(en.auth.login.email)).not.toBeInTheDocument();
    release();
    expect(await screen.findByLabelText(en.auth.login.email)).toBeInTheDocument();
  });

  it("redirects a signed-out visitor to /login and remembers the path", async () => {
    await renderApp("/trips?tab=2", { backend: mockBackend({ user: null }) });

    expect(screen.getByRole("heading", { level: 1, name: en.auth.login.title })).toBeInTheDocument();
    expect(currentLocation()).toBe("/login?next=%2Ftrips%3Ftab%3D2");
  });

  it("offers a retry when the session check fails", async () => {
    const backend = mockBackend();
    backend.routes["GET /auth/me"] = () => empty(503);
    await renderApp("/", { backend });

    expect(screen.getByRole("alert")).toHaveTextContent(en.auth.sessionError.message);

    backend.routes["GET /auth/me"] = () => json(USERS.admin);
    await userEvent.click(screen.getByRole("button", { name: en.auth.sessionError.retry }));
    expect(await screen.findByRole("heading", { level: 1, name: en.dashboard.title })).toBeInTheDocument();
  });

  it("redirects a signed-in user away from /login", async () => {
    await renderApp("/login", { backend: mockBackend({ user: USERS.admin }) });
    expect(currentLocation()).toBe("/");
  });
});

describe("login page", () => {
  it("focuses the email field and labels the fields for browsers and screen readers", async () => {
    await renderApp("/login", { backend: mockBackend({ user: null }) });

    const email = screen.getByLabelText(en.auth.login.email);
    const password = screen.getByLabelText(en.auth.login.password);
    expect(email).toHaveFocus();
    expect(email).toHaveAttribute("autocomplete", "username");
    expect(password).toHaveAttribute("autocomplete", "current-password");
    expect(password).toHaveAttribute("type", "password");
  });

  it("shows the theme and language pickers", async () => {
    await renderApp("/login", { backend: mockBackend({ user: null }) });

    expect(screen.getByLabelText(en.theme.label)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(en.language.label), "fi");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(fi.auth.login.title);
  });

  it("signs in, sends JSON with the CSRF header, and returns to the original path", async () => {
    const backend = mockBackend({ user: null, loginAs: USERS.planner });
    await renderApp("/trips", { backend });
    expect(currentLocation()).toBe("/login?next=%2Ftrips");

    await signIn();

    expect(await screen.findByRole("heading", { level: 1, name: en.nav.items.trips })).toBeInTheDocument();
    expect(currentLocation()).toBe("/trips");
    const [call] = backend.callsTo("POST", "/auth/login");
    expect(call?.headers.get(CSRF_HEADER_NAME)).toBe("fleetfreight");
    expect(JSON.parse(call?.body ?? "{}")).toEqual({ email: USERS.planner.email, password: "demo-password" });
  });

  it.each(["https://evil.example.com/", "//evil.example.com", "/\\evil.example.com"])(
    "ignores the external return path %s",
    async (next) => {
      await renderApp(`/login?next=${encodeURIComponent(next)}`, { backend: mockBackend({ user: null }) });
      await signIn();
      expect(await screen.findByRole("heading", { level: 1, name: en.dashboard.title })).toBeInTheDocument();
      expect(currentLocation()).toBe("/");
    },
  );

  it("shows a generic error on 401, clears the password and keeps the user on the page", async () => {
    const backend = mockBackend({ user: null });
    backend.routes["POST /auth/login"] = () => empty(401);
    await renderApp("/login", { backend });

    await signIn(USERS.planner.email, "wrong");

    expect(await screen.findByRole("alert")).toHaveTextContent(en.auth.errors.invalid);
    expect(screen.getByLabelText(en.auth.login.password)).toHaveValue("");
    expect(screen.getByLabelText(en.auth.login.password)).toHaveFocus();
    expect(screen.getByLabelText(en.auth.login.email)).toHaveValue(USERS.planner.email);
    expect(currentLocation()).toBe("/login");
    // A 401 from the login attempt must not be mistaken for an expired session.
    expect(screen.queryByText(en.auth.notices.expired)).not.toBeInTheDocument();
  });

  it("shows the wait time from Retry-After on 429", async () => {
    const backend = mockBackend({ user: null });
    backend.routes["POST /auth/login"] = () => empty(429, { "Retry-After": "30" });
    await renderApp("/login", { backend });

    await signIn();

    expect(await screen.findByRole("alert")).toHaveTextContent("Too many failed attempts. Try again in 30 seconds.");
  });

  it("rounds long waits up to minutes, in the UI language", async () => {
    const backend = mockBackend({ user: null });
    backend.routes["POST /auth/login"] = () => empty(429, { "Retry-After": "61" });
    await renderApp("/login", { backend });
    await userEvent.selectOptions(screen.getByLabelText(en.language.label), "fi");

    await userEvent.type(screen.getByLabelText(fi.auth.login.email), "a@demo.example.com");
    await userEvent.type(screen.getByLabelText(fi.auth.login.password), "x");
    await userEvent.click(screen.getByRole("button", { name: fi.auth.login.submit }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Yritä uudelleen: 2 minuuttia/);
  });

  it("handles a 429 without a usable Retry-After", async () => {
    const backend = mockBackend({ user: null });
    backend.routes["POST /auth/login"] = () => empty(429);
    await renderApp("/login", { backend });
    await signIn();
    expect(await screen.findByRole("alert")).toHaveTextContent(en.auth.errors.rateLimitedNoWait);
  });

  it("shows a network error", async () => {
    const backend = mockBackend({ user: null });
    backend.routes["POST /auth/login"] = () => {
      throw new TypeError("Failed to fetch");
    };
    await renderApp("/login", { backend });
    await signIn();
    expect(await screen.findByRole("alert")).toHaveTextContent(en.auth.errors.network);
  });

  it("validates empty fields without calling the server", async () => {
    const backend = mockBackend({ user: null });
    await renderApp("/login", { backend });

    await userEvent.click(screen.getByRole("button", { name: en.auth.login.submit }));

    expect(screen.getByRole("alert")).toHaveTextContent(en.auth.errors.validation);
    expect(backend.callsTo("POST", "/auth/login")).toHaveLength(0);
  });

  it("disables the button while the request runs", async () => {
    const backend = mockBackend({ user: null });
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    backend.routes["POST /auth/login"] = async () => {
      await gate;
      return empty(401);
    };
    await renderApp("/login", { backend });
    await signIn();

    expect(screen.getByRole("button", { name: en.auth.login.submitting })).toBeDisabled();
    release();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: en.auth.login.submit })).toBeEnabled();
    });
  });
});

describe("session in progress", () => {
  it("a 401 mid-session resets the state and redirects to login with the current path", async () => {
    const backend = mockBackend({ user: USERS.planner });
    await renderApp("/trips", { backend });
    expect(screen.getByRole("heading", { level: 1, name: en.nav.items.trips })).toBeInTheDocument();

    backend.user = null; // the session expires on the server
    // Any request made through the shared client does it, no view needs its own 401 handling.
    await act(async () => {
      await api.GET("/auth/me");
    });

    expect(await screen.findByRole("heading", { level: 1, name: en.auth.login.title })).toBeInTheDocument();
    expect(screen.getByText(en.auth.notices.expired)).toBeInTheDocument();
    expect(currentLocation()).toBe("/login?next=%2Ftrips");

    // Signing in again returns to where the user was.
    await signIn();
    expect(await screen.findByRole("heading", { level: 1, name: en.nav.items.trips })).toBeInTheDocument();
    expect(currentLocation()).toBe("/trips");
  });

  it("signs out: calls logout with the CSRF header, shows the login page, and does not remember the path", async () => {
    const backend = mockBackend({ user: USERS.planner });
    await renderApp("/trips", { backend });

    await userEvent.click(screen.getByRole("button", { name: en.auth.logout }));

    expect(await screen.findByRole("heading", { level: 1, name: en.auth.login.title })).toBeInTheDocument();
    expect(screen.getByText(en.auth.notices.loggedOut)).toBeInTheDocument();
    expect(currentLocation()).toBe("/login");
    expect(backend.callsTo("POST", "/auth/logout")[0]?.headers.get(CSRF_HEADER_NAME)).toBe("fleetfreight");
  });

  it("treats a 401 on logout (stale session) as signed out", async () => {
    const backend = mockBackend({ user: USERS.planner });
    backend.routes["POST /auth/logout"] = () => empty(401);
    await renderApp("/", { backend });

    await userEvent.click(screen.getByRole("button", { name: en.auth.logout }));

    expect(await screen.findByLabelText(en.auth.login.email)).toBeInTheDocument();
    expect(screen.getByText(en.auth.notices.loggedOut)).toBeInTheDocument();
  });

  it("stays signed in and tells the user when logout fails", async () => {
    const backend = mockBackend({ user: USERS.planner });
    backend.routes["POST /auth/logout"] = () => empty(500);
    await renderApp("/", { backend });

    await userEvent.click(screen.getByRole("button", { name: en.auth.logout }));

    expect(await screen.findByRole("alert")).toHaveTextContent(en.auth.logoutFailed);
    expect(screen.getByText(USERS.planner.email)).toBeInTheDocument();
  });
});

describe("top bar user", () => {
  it("shows the email and the translated role", async () => {
    await renderApp("/", { backend: mockBackend({ user: USERS.planner }) });
    const group = screen.getByRole("group", { name: en.auth.user.label });
    expect(within(group).getByText(USERS.planner.email)).toBeInTheDocument();
    expect(within(group).getByText(en.auth.roles.planner)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(en.language.label), "fi");
    expect(within(screen.getByRole("group", { name: fi.auth.user.label })).getByText(fi.auth.roles.planner)).toBeInTheDocument();
  });
});

describe("roles in the UI", () => {
  it("shows the administration links to admins only", async () => {
    const { unmount } = await renderApp("/", { backend: mockBackend({ user: USERS.admin }) });
    expect(screen.getByRole("link", { name: en.nav.items.pricing })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: en.nav.sections.administration })).toBeInTheDocument();
    unmount();

    for (const user of [USERS.planner, USERS.viewer]) {
      const { unmount: done } = await renderApp("/", { backend: mockBackend({ user }) });
      expect(screen.queryByRole("link", { name: en.nav.items.pricing })).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: en.nav.sections.administration })).not.toBeInTheDocument();
      // Other sections stay visible.
      expect(screen.getByRole("link", { name: en.nav.items.orders })).toBeInTheDocument();
      done();
    }
  });

  it("shows a no-access view when a non-admin opens an administration path directly", async () => {
    await renderApp("/pricing", { backend: mockBackend({ user: USERS.viewer }) });
    expect(screen.getByRole("heading", { level: 1, name: en.forbidden.title })).toBeInTheDocument();
  });

  it("lets admins open administration views", async () => {
    await renderApp("/pricing", { backend: mockBackend({ user: USERS.admin }) });
    expect(screen.getByRole("heading", { level: 1, name: en.nav.items.pricing })).toBeInTheDocument();
  });
});
