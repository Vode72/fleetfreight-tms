/** "30 seconds" / "2 minutes" in the UI language. Rounds minutes up so the user never retries too early. */
export function formatWait(seconds: number, locale: string): string {
  const inMinutes = seconds >= 60;
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: inMinutes ? "minute" : "second",
    unitDisplay: "long",
  }).format(inMinutes ? Math.ceil(seconds / 60) : seconds);
}
