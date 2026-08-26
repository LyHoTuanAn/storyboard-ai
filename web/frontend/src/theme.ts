export type ThemeMode = "light" | "dark" | "system";

const STORAGE_KEY = "sb-theme";

export function getStoredTheme(): ThemeMode {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "light" || value === "dark" || value === "system") return value;
  } catch {
    // localStorage co the bi chan; roi ve system
  }
  return "system";
}

export function applyTheme(mode: ThemeMode): void {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const dark = mode === "dark" || (mode === "system" && prefersDark);
  document.documentElement.classList.toggle("dark", dark);
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // khong luu duoc thi thoi
  }
}
