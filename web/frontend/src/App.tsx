import { useEffect, useState } from "react";
import { MoonIcon, SunIcon } from "@phosphor-icons/react";
import { applyTheme, getStoredTheme, type ThemeMode } from "./theme";
import { JobForm } from "./components/JobForm";

export default function App() {
  const [mode, setMode] = useState<ThemeMode>(getStoredTheme);
  const [selected, setSelected] = useState<string | null>(null);
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
      <main className="mx-auto mt-6 grid max-w-[1400px] gap-8 md:grid-cols-[320px_1fr]">
        <aside>
          <h2 className="mb-4 text-sm font-semibold">Job moi</h2>
          <JobForm onCreated={(id) => setSelected(id)} />
        </aside>
        <section>
          {selected ? (
            <p className="mono text-sm">Da tao job {selected}</p>
          ) : (
            <p className="mono text-sm" style={{ color: "var(--text-dim)" }}>
              Chua chon job nao.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
