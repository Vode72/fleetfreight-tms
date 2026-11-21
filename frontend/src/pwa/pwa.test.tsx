import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useNavigate } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import en from "../i18n/en.json";
import { registered } from "../test/pwaRegisterStub";
import { InstallApp } from "./InstallApp";
import { PwaNotices } from "./PwaNotices";
import { startServiceWorker } from "./serviceWorker";

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(navigator, "serviceWorker");
});

function GoTo({ path }: { path: string }) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => {
        void navigate(path);
      }}
    >
      go
    </button>
  );
}

function renderNotices() {
  return render(
    <MemoryRouter initialEntries={["/orders"]}>
      <PwaNotices />
      <GoTo path="/trips" />
    </MemoryRouter>,
  );
}

describe("install (D88)", () => {
  it("shows the browser-menu hint where no install prompt exists (Firefox, Safari)", () => {
    render(<InstallApp />);
    expect(screen.getByText(en.pwa.installHelp)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: en.pwa.install })).not.toBeInTheDocument();
  });

  it("shows the install button when the browser offers a prompt (Chrome, Edge, Opera)", async () => {
    render(<InstallApp />);
    const prompt = vi.fn(() => Promise.resolve());
    const event = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), {
      prompt,
      userChoice: Promise.resolve({ outcome: "accepted" as const }),
    });
    act(() => {
      window.dispatchEvent(event);
    });
    expect(event.defaultPrevented).toBe(true);

    await userEvent.click(screen.getByRole("button", { name: en.pwa.install }));
    expect(prompt).toHaveBeenCalledOnce();
    // A prompt can be used once; afterwards the hint is shown again.
    expect(screen.queryByRole("button", { name: en.pwa.install })).not.toBeInTheDocument();
  });

  it("hides everything once the app is installed", () => {
    const { container } = render(<InstallApp />);
    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("shows nothing when running as an installed app", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({ matches: query === "(display-mode: standalone)" })),
    );
    const { container } = render(<InstallApp />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("connection and update notices (D88)", () => {
  it("shows the offline banner only while there is no connection", () => {
    renderNotices();
    expect(screen.queryByText(en.pwa.offline)).not.toBeInTheDocument();

    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    expect(screen.getByText(en.pwa.offline)).toBeInTheDocument();

    vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
    act(() => {
      window.dispatchEvent(new Event("online"));
    });
    expect(screen.queryByText(en.pwa.offline)).not.toBeInTheDocument();
  });

  it("asks before taking a new version into use", async () => {
    Object.defineProperty(navigator, "serviceWorker", { value: {}, configurable: true });
    startServiceWorker();
    renderNotices();
    expect(screen.queryByText(en.pwa.updateAvailable)).not.toBeInTheDocument();

    act(() => {
      registered.options?.onNeedRefresh?.();
    });
    expect(screen.getByText(en.pwa.updateAvailable)).toBeInTheDocument();
    expect(registered.reloads).toBe(0); // nothing reloads on its own

    // "Later" hides the prompt until the user moves to another page.
    await userEvent.click(screen.getByRole("button", { name: en.pwa.later }));
    expect(screen.queryByText(en.pwa.updateAvailable)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "go" }));
    expect(screen.getByText(en.pwa.updateAvailable)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: en.pwa.reload }));
    expect(registered.reloads).toBe(1);
  });

  it("keeps the live region in the page so notices are announced", () => {
    renderNotices();
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).not.toHaveTextContent(en.pwa.offline);
  });
});

describe("service worker configuration (D88)", () => {
  it("caches only the app's own files, never API or sign-in responses", () => {
    const files = import.meta.glob<string>("../../vite.config.ts", {
      query: "?raw",
      import: "default",
      eager: true,
    });
    const config = Object.values(files)[0] ?? "";
    expect(config).toContain("runtimeCaching: []");
    expect(config).toContain("navigateFallbackDenylist: [/^\\/api\\//]");
    expect(config).toContain('registerType: "prompt"');
  });
});
