/**
 * Detects literal colours in CSS and TS/TSX source. Used by noHardcodedColors.test.ts to keep
 * components on design tokens. Lives in src/theme/ because it must contain colour names.
 *
 * Allowed as colours in CSS values: var(--...), transparent, currentColor, inherit, initial,
 * unset and none. Everything that is a literal colour (hex, rgb/hsl/..., any CSS named colour)
 * is reported.
 */

const NAMED_COLORS = [
  "aliceblue", "antiquewhite", "aqua", "aquamarine", "azure", "beige", "bisque", "black",
  "blanchedalmond", "blue", "blueviolet", "brown", "burlywood", "cadetblue", "chartreuse",
  "chocolate", "coral", "cornflowerblue", "cornsilk", "crimson", "cyan", "darkblue", "darkcyan",
  "darkgoldenrod", "darkgray", "darkgreen", "darkgrey", "darkkhaki", "darkmagenta",
  "darkolivegreen", "darkorange", "darkorchid", "darkred", "darksalmon", "darkseagreen",
  "darkslateblue", "darkslategray", "darkslategrey", "darkturquoise", "darkviolet", "deeppink",
  "deepskyblue", "dimgray", "dimgrey", "dodgerblue", "firebrick", "floralwhite", "forestgreen",
  "fuchsia", "gainsboro", "ghostwhite", "gold", "goldenrod", "gray", "green", "greenyellow",
  "grey", "honeydew", "hotpink", "indianred", "indigo", "ivory", "khaki", "lavender",
  "lavenderblush", "lawngreen", "lemonchiffon", "lightblue", "lightcoral", "lightcyan",
  "lightgoldenrodyellow", "lightgray", "lightgreen", "lightgrey", "lightpink", "lightsalmon",
  "lightseagreen", "lightskyblue", "lightslategray", "lightslategrey", "lightsteelblue",
  "lightyellow", "lime", "limegreen", "linen", "magenta", "maroon", "mediumaquamarine",
  "mediumblue", "mediumorchid", "mediumpurple", "mediumseagreen", "mediumslateblue",
  "mediumspringgreen", "mediumturquoise", "mediumvioletred", "midnightblue", "mintcream",
  "mistyrose", "moccasin", "navajowhite", "navy", "oldlace", "olive", "olivedrab", "orange",
  "orangered", "orchid", "palegoldenrod", "palegreen", "paleturquoise", "palevioletred",
  "papayawhip", "peachpuff", "peru", "pink", "plum", "powderblue", "purple", "rebeccapurple",
  "red", "rosybrown", "royalblue", "saddlebrown", "salmon", "sandybrown", "seagreen", "seashell",
  "sienna", "silver", "skyblue", "slateblue", "slategray", "slategrey", "snow", "springgreen",
  "steelblue", "tan", "teal", "thistle", "tomato", "turquoise", "violet", "wheat", "white",
  "whitesmoke", "yellow", "yellowgreen",
];

// Whole words only: "read-only", "--status-red" and "white-space" must not match.
const NAMED = new RegExp(`(?<![\\w-])(?:${NAMED_COLORS.join("|")})(?![\\w-])`, "i");
const HEX = /#[0-9a-fA-F]{3,8}\b/;
const FUNCTIONAL = /\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color-mix|light-dark)\(/i;

/** A hex-like anchor, such as href="#face" or url(#add), is not a colour. */
const ANCHOR_CONTEXT = /(?:\b(?:href|xlinkHref|to|id|htmlFor|name|form|list|key)|\baria-[\w-]+)\s*=\s*\{?\s*["'`]$|url\(\s*["']?$/;

/** Reports literal colours in one CSS value. Tokens (`--name`) are removed first. */
function colorsInValue(value: string): string[] {
  const cleaned = value
    .replace(/(["'])(?:\\.|(?!\1).)*\1/g, " ") // strings, e.g. content: "red"
    .replace(/url\([^)]*\)/gi, " ")
    .replace(/--[\w-]+/g, " "); // var(--token), --token
  return [HEX.exec(cleaned)?.[0], FUNCTIONAL.exec(cleaned)?.[0], NAMED.exec(cleaned)?.[0]].filter(
    (hit): hit is string => hit !== undefined,
  );
}

/** Literal colours in a CSS file, as readable strings. */
export function findCssColorViolations(css: string): string[] {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const found: string[] = [];
  for (const [, property, value] of withoutComments.matchAll(/([\w-]+)\s*:\s*([^;{}]+)/g)) {
    if (property === undefined || value === undefined) continue;
    for (const hit of colorsInValue(value)) found.push(`${property}: ${hit}`);
  }
  return found;
}

const SVG_COLOR_ATTRIBUTES = "fill|stroke|color|stopColor|floodColor|lightingColor|bgcolor";
const ALLOWED_ATTRIBUTE_VALUES = /^(?:none|currentColor|transparent|inherit|initial|unset|var\(--[\w-]+\)|url\(#[\w-]+\))$/i;
const COLOR_KEYS =
  "color|background(?:Color)?|border(?:Top|Right|Bottom|Left)?(?:Color)?|outline(?:Color)?|boxShadow|textShadow|fill|stroke|stopColor|caretColor|accentColor";

function stringLiterals(text: string): string[] {
  return [...text.matchAll(/(["'`])((?:\\.|(?!\1)[^\\])*)\1/g)].map((match) => match[2] ?? "");
}

/** Text of the object literal that starts at the `{` at `start`, or "" if unbalanced. */
function balancedBraces(source: string, start: number): string {
  let depth = 0;
  for (let i = start; i < source.length; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}" && --depth === 0) return source.slice(start, i + 1);
  }
  return "";
}

/** Literal colours in TS or TSX source: style props, SVG attributes, colour keys, hex and functions. */
export function findScriptColorViolations(source: string): string[] {
  const found: string[] = [];

  // Hex colours and colour functions anywhere, except anchors such as href="#face".
  for (const match of source.matchAll(new RegExp(HEX.source, "g"))) {
    if (!ANCHOR_CONTEXT.test(source.slice(Math.max(0, match.index - 40), match.index))) found.push(match[0]);
  }
  const functional = FUNCTIONAL.exec(source);
  if (functional) found.push(functional[0]);

  // SVG colour attributes: only tokens, currentColor, none and url(#id) are allowed.
  const attribute = new RegExp(
    `\\b(${SVG_COLOR_ATTRIBUTES})\\s*=\\s*(?:"([^"]*)"|'([^']*)'|\\{\\s*(?:"([^"]*)"|'([^']*)'|\`([^\`]*)\`)\\s*\\})`,
    "g",
  );
  for (const match of source.matchAll(attribute)) {
    const value = (match[2] ?? match[3] ?? match[4] ?? match[5] ?? match[6] ?? "").trim();
    if (!ALLOWED_ATTRIBUTE_VALUES.test(value)) found.push(`${match[1] ?? "attribute"}=${value}`);
  }

  // style={{ ... }}: every string literal in the object is a CSS value.
  for (const match of source.matchAll(/\bstyle\s*=\s*\{\s*\{/g)) {
    const objectStart = source.indexOf("{", match.index + match[0].indexOf("{") + 1);
    for (const literal of stringLiterals(balancedBraces(source, objectStart))) found.push(...colorsInValue(literal));
  }

  // Colour-like keys in any object, e.g. const s = { background: "tomato" }.
  const keyed = new RegExp(`(?<![\\w.])(?:${COLOR_KEYS})\\s*:\\s*(["'\`])((?:\\\\.|(?!\\1)[^\\\\])*)\\1`, "g");
  for (const match of source.matchAll(keyed)) found.push(...colorsInValue(match[2] ?? ""));

  return found;
}
