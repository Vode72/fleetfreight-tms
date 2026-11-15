/** Where to go after login when no valid return path was given. */
export const DEFAULT_RETURN_PATH = "/";
export const LOGIN_PATH = "/login";
export const RETURN_PARAM = "next";

const PLACEHOLDER_ORIGIN = "https://return-path.invalid";

function hasControlCharacter(value: string): boolean {
  for (const char of value) {
    const code = char.charCodeAt(0);
    if (code <= 0x1f || code === 0x7f) return true;
  }
  return false;
}

/**
 * Accepts only an in-app path ("/orders?x=1#y") as a post-login destination. Anything that could
 * leave this origin (absolute URLs, protocol-relative "//host", backslash tricks, control
 * characters that browsers strip) falls back to the default. Prevents open redirects.
 */
export function safeReturnPath(raw: string | null | undefined): string {
  if (!raw?.startsWith("/")) return DEFAULT_RETURN_PATH;
  if (raw.startsWith("//") || raw.includes("\\") || hasControlCharacter(raw)) return DEFAULT_RETURN_PATH;

  let url: URL;
  try {
    url = new URL(raw, PLACEHOLDER_ORIGIN);
  } catch {
    return DEFAULT_RETURN_PATH;
  }
  if (url.origin !== PLACEHOLDER_ORIGIN) return DEFAULT_RETURN_PATH;
  if (url.pathname === LOGIN_PATH) return DEFAULT_RETURN_PATH;
  return `${url.pathname}${url.search}${url.hash}`;
}

/** Builds the login URL that remembers where the user was heading. */
export function loginUrlFor(location: { pathname: string; search: string; hash: string }): string {
  const target = safeReturnPath(`${location.pathname}${location.search}${location.hash}`);
  if (target === DEFAULT_RETURN_PATH) return LOGIN_PATH;
  return `${LOGIN_PATH}?${new URLSearchParams({ [RETURN_PARAM]: target }).toString()}`;
}
