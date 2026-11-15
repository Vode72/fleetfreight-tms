// Applies the remembered theme and language before first paint (no flash).
// Loaded as a blocking classic script from <head> so a Content-Security-Policy of
// script-src 'self' works without inline scripts.
// Keys must match THEME_STORAGE_KEY and LANGUAGE_STORAGE_KEY (checked by tests).
try {
  var theme = localStorage.getItem("ff.theme");
  if (theme === "business-light" || theme === "control-dark") {
    document.documentElement.setAttribute("data-theme", theme);
  }
  var lang = localStorage.getItem("ff.language");
  if (lang === "en" || lang === "fi") document.documentElement.lang = lang;
} catch (e) {}
