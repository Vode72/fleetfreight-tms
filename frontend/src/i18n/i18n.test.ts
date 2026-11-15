import { describe, expect, it } from "vitest";

import i18n, { setLanguage } from "./index";
import en from "./en.json";
import fi from "./fi.json";

/** Flattens nested translation objects to dotted key paths. */
function keyPaths(node: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(node).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof value === "object" && value !== null
      ? keyPaths(value as Record<string, unknown>, path)
      : [path];
  });
}

function leafValues(node: Record<string, unknown>): string[] {
  return Object.values(node).flatMap((value) =>
    typeof value === "object" && value !== null ? leafValues(value as Record<string, unknown>) : [String(value)],
  );
}

describe("translations", () => {
  it("en and fi have exactly the same keys", () => {
    expect(keyPaths(fi).sort()).toEqual(keyPaths(en).sort());
  });

  it("has no empty translations", () => {
    for (const file of [en, fi]) {
      expect(leafValues(file).every((v) => v.trim() !== "")).toBe(true);
    }
  });

  it("defaults to English and switches language programmatically", async () => {
    expect(i18n.language).toBe("en");
    await setLanguage("fi");
    expect(i18n.t("health.retry")).toBe(fi.health.retry);
    await setLanguage("en");
    expect(i18n.t("health.retry")).toBe(en.health.retry);
  });
});
