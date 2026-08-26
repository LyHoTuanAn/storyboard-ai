import { useEffect, useState } from "react";
import { MoonIcon, SunIcon } from "@phosphor-icons/react";
import { applyTheme, getStoredTheme, type ThemeMode } from "./theme";

export default function App() {
  const [mode, setMode] = useState<ThemeMode>(getStoredTheme);
  const nextLabel = mode === "dark" ? "Chuyen sang giao dien sang" : "Chuyen sang giao dien toi";

  useEffect(() => {
    applyTheme(mode);
  }, [mode]);

  return (
    <div className="min-h-[100dvh] p-6">
      <header className="flex items-center justify-between border-b pb-4" style={{ borderColor: "var(--border)" }}>
        <h1 className="text-lg font-semibold">Storyboard AI</h1>
        <button
          type="button"
          onClick={() => setMode(mode === "dark" ? "light" : "dark")}
          className="px-3 py-2 transition-transform active:scale-[0.98]"
          style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
          aria-label={nextLabel}
        >
          {mode === "dark" ? <SunIcon size={18} /> : <MoonIcon size={18} />}
        </button>
      </header>
      <p className="mono mt-6" style={{ color: "var(--text-dim)" }}>
        Khung giao dien da san sang.
      </p>
    </div>
  );
}
