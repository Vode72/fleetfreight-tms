import { describe, expect, it } from "vitest";

import { THEMES } from "./theme";
import css from "./tokens.css?raw";

/** Extracts `--name: #rrggbb;` declarations from the block of one theme. */
function themeTokens(theme: string): Record<string, string> {
  const block = new RegExp(`\\[data-theme="${theme}"\\]\\s*\\{([\\s\\S]*?)\\n\\}`).exec(css)?.[1];
  if (block === undefined) throw new Error(`Theme block not found: ${theme}`);
  const tokens: Record<string, string> = {};
  for (const [, name, value] of block.matchAll(/(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    if (name !== undefined && value !== undefined) tokens[name] = value;
  }
  return tokens;
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * (channels[0] ?? 0) + 0.7152 * (channels[1] ?? 0) + 0.0722 * (channels[2] ?? 0);
}

function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

const SURFACES = ["--bg-main", "--panel-bg", "--panel-header"] as const;
const STATUSES = ["planned", "confirmed", "in-progress", "delivered", "invoiced", "cancelled"];
const SEVERITIES = ["red", "orange", "yellow"];
const BADGES = ["adr", "gdp", "thermo"];
const CAPACITY = ["ok", "warn", "over"];

type Pair = [foreground: string, background: string, minimum: number];

function pairsFor(theme: string): Pair[] {
  const pairs: Pair[] = [];
  for (const surface of SURFACES) {
    pairs.push(["--text-main", surface, 4.5], ["--text-muted-strong", surface, 4.5], ["--accent-text", surface, 4.5]);
    pairs.push(["--focus-ring", surface, 3]);
  }
  // Base muted text and accent: AA on the main panel surface (documented limitation elsewhere).
  pairs.push(["--text-muted", "--panel-bg", 4.5], ["--accent", "--panel-bg", 4.5]);
  if (theme === "control-dark") pairs.push(["--text-muted", "--bg-main", 4.5], ["--accent", "--bg-main", 4.5]);
  pairs.push(["--accent-contrast", "--accent", 4.5]);
  pairs.push(["--text-main", "--surface-hover", 4.5], ["--text-main", "--surface-selected", 4.5]);
  pairs.push(["--text-muted-strong", "--surface-hover", 4.5], ["--accent-text", "--surface-selected", 4.5]);
  for (const s of STATUSES) pairs.push([`--status-${s}`, `--status-${s}-bg`, 4.5], [`--status-${s}`, "--panel-bg", 4.5]);
  for (const s of SEVERITIES) pairs.push([`--severity-${s}`, `--severity-${s}-bg`, 4.5], [`--severity-${s}`, "--panel-bg", 4.5]);
  for (const b of BADGES) pairs.push([`--badge-${b}`, `--badge-${b}-bg`, 4.5], [`--badge-${b}`, "--panel-bg", 4.5]);
  for (const c of CAPACITY) pairs.push([`--capacity-${c}`, "--capacity-track", 3], [`--capacity-${c}`, "--panel-bg", 3]);
  return pairs;
}

describe.each(THEMES)("contrast in %s", (theme) => {
  const tokens = themeTokens(theme);

  it("defines every token the other themes define", () => {
    const other = THEMES.find((t) => t !== theme);
    if (other === undefined) throw new Error("expected two themes");
    expect(Object.keys(tokens).sort()).toEqual(Object.keys(themeTokens(other)).sort());
  });

  it.each(pairsFor(theme))("%s on %s is at least %s:1", (fg, bg, minimum) => {
    const foreground = tokens[fg];
    const background = tokens[bg];
    if (foreground === undefined || background === undefined) throw new Error(`Missing token ${fg} or ${bg}`);
    expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(minimum);
  });
});
