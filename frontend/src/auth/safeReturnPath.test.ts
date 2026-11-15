import { describe, expect, it } from "vitest";

import { loginUrlFor, safeReturnPath } from "./safeReturnPath";

describe("safeReturnPath", () => {
  it.each([
    ["/orders", "/orders"],
    ["/orders?status=open#top", "/orders?status=open#top"],
    ["/", "/"],
  ])("keeps the in-app path %s", (input, expected) => {
    expect(safeReturnPath(input)).toBe(expected);
  });

  it.each([
    null,
    undefined,
    "",
    "orders",
    "https://evil.example.com/",
    "http://evil.example.com",
    "//evil.example.com",
    "///evil.example.com",
    "/\\evil.example.com",
    "\\\\evil.example.com",
    "/\t/evil.example.com",
    "/\n/evil.example.com",
    "javascript:alert(1)",
    "/login",
    "/login?next=/orders",
  ])("falls back to / for %j", (input) => {
    expect(safeReturnPath(input)).toBe("/");
  });
});

describe("loginUrlFor", () => {
  it("remembers the page the user was heading to", () => {
    expect(loginUrlFor({ pathname: "/trips", search: "?a=1", hash: "" })).toBe("/login?next=%2Ftrips%3Fa%3D1");
  });

  it("stays plain for the front page", () => {
    expect(loginUrlFor({ pathname: "/", search: "", hash: "" })).toBe("/login");
  });
});
