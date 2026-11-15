import { describe, expect, it } from "vitest";

import { findCssColorViolations, findScriptColorViolations } from "./colorLint";

// Every CSS, TS and TSX file under src/ except src/theme/ (where the tokens live), tests, and the
// generated API schema.
const sources = import.meta.glob<string>(
  ["/src/**/*.{css,ts,tsx}", "!/src/theme/**", "!/src/**/*.test.{ts,tsx}", "!/src/api/schema.ts"],
  { query: "?raw", import: "default", eager: true },
);

describe("no hard-coded colours outside src/theme", () => {
  const entries = Object.entries(sources);

  it("scans the source files", () => {
    expect(entries.length).toBeGreaterThan(20);
    expect(entries.some(([path]) => path.endsWith(".ts"))).toBe(true);
    expect(entries.some(([path]) => path.endsWith(".tsx"))).toBe(true);
    expect(entries.some(([path]) => path.endsWith(".css"))).toBe(true);
  });

  it.each(entries)("%s", (path, text) => {
    const violations = path.endsWith(".css") ? findCssColorViolations(text) : findScriptColorViolations(text);
    expect(violations).toEqual([]);
  });
});

describe("colour lint detection", () => {
  const cssMustFail = [
    "a { border: 1px solid red; }",
    "a { box-shadow: 0 0 2px black; }",
    "a { background: linear-gradient(red, blue); }",
    "a { color: tomato; }",
    "a { color: #fff; }",
    "a { color: #FA0; }",
    "a{color:rgb(1 2 3)}",
    "a { color: var(--x, red); }",
    "a { outline: 2px solid RebeccaPurple; }",
    "a { --tone: #123456; }",
  ];
  const cssMustPass = [
    "a { color: var(--text-main); }",
    "a { background: transparent; border-color: currentColor; }",
    "a { white-space: nowrap; border: 1px solid var(--border); }",
    "a { color: inherit; border: none; }",
    "/* color: red */ a { margin: 0; }",
    'a::before { content: "red"; }',
    ".x { --tone: var(--status-red); }",
    "a:focus-visible { outline: 2px solid var(--focus-ring); }",
    ".red, .read-only { margin: 0; }",
    "a { font-family: system-ui, sans-serif; }",
  ];
  const scriptMustFail = [
    '<div style={{ color: "red" }} />',
    '<path fill="red" />',
    '<path stroke={"#abc"} />',
    '<stop stopColor="blue" />',
    'const s = { background: "tomato" };',
    'const c = "#ff0000";',
    '<div style={{ border: "1px solid black" }} />',
    "const c = `rgb(0 0 0)`;",
    '<div style={{ boxShadow: "0 0 2px #000" }} />',
  ];
  const scriptMustPass = [
    '<a href="#face">x</a>',
    '<a href="#main">x</a>',
    '<a to="#bad">x</a>',
    '<label htmlFor="#add" />',
    '<path fill="none" stroke="currentColor" />',
    '<path fill="url(#grad)" />',
    '<path fill="var(--accent)" />',
    '<div style={{ width: "45%" }} />',
    '<div style={{ "--tone": "var(--x)" }} />',
    'const label = "red alert";',
  ];

  it.each(cssMustFail)("CSS is caught: %s", (input) => {
    expect(findCssColorViolations(input).length).toBeGreaterThan(0);
  });
  it.each(cssMustPass)("CSS is allowed: %s", (input) => {
    expect(findCssColorViolations(input)).toEqual([]);
  });
  it.each(scriptMustFail)("TS/TSX is caught: %s", (input) => {
    expect(findScriptColorViolations(input).length).toBeGreaterThan(0);
  });
  it.each(scriptMustPass)("TS/TSX is allowed: %s", (input) => {
    expect(findScriptColorViolations(input)).toEqual([]);
  });
});
