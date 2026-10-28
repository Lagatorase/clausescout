// Light, dark or follow the system. The choice is a per-browser convenience, so storage
// failures (private windows, blocked storage) just fall back to the system setting.
export type Theme = "system" | "light" | "dark";

export function loadTheme(): Theme {
  try {
    const t = localStorage.getItem("clausescout-theme");
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  try {
    localStorage.setItem("clausescout-theme", theme);
  } catch {
    // Nothing to do: the theme still applies for this visit.
  }
}

export const nextTheme = (t: Theme): Theme =>
  t === "system" ? "light" : t === "light" ? "dark" : "system";
