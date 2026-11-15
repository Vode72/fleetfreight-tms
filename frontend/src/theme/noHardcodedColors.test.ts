import { describe, expect, it } from "vitest";

// Every CSS and TSX file under src/ except src/theme/ (where the tokens live).
const sources = import.meta.glob<string>(["/src/**/*.{css,tsx}", "!/src/theme/**"], {
  query: "?raw",
  import: "default",
  eager: true,
});

const HEX = /#[0-9a-fA-F]{3,8}\b/;
const FUNCTIONAL = /\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color-mix)\(/i;
const NAMED = /:\s*(?:white|black|red|green|blue|orange|yellow|gray|grey|purple|pink|brown|navy|teal|cyan|silver)\b/i;

describe("no hard-coded colours outside src/theme", () => {
  const entries = Object.entries(sources);

  it("scans the source files", () => {
    expect(entries.length).toBeGreaterThan(5);
  });

  it.each(entries)("%s", (path, text) => {
    expect(HEX.exec(text)?.[0]).toBeUndefined();
    expect(FUNCTIONAL.exec(text)?.[0]).toBeUndefined();
    if (path.endsWith(".css")) expect(NAMED.exec(text)?.[0]).toBeUndefined();
  });
});
