import { useEffect, useState } from "react";
import { MoonIcon, SunIcon } from "@phosphor-icons/react";
import { applyTheme, getStoredTheme, type ThemeMode } from "./theme";
import { JobForm } from "./components/JobForm";
import { JobList } from "./components/JobList";
import { JobDetail } from "./components/JobDetail";
import { EmptyState } from "./components/EmptyState";
import { HealthBanner } from "./components/HealthBanner";
import { useJobs } from "./hooks/useJobs";

export default function App() {
  const [mode, setMode] = useState<ThemeMode>(getStoredTheme);
  const [selected, setSelected] = useState<string | null>(null);
  const { jobs, refresh } = useJobs();
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
      <div className="mx-auto mt-6 max-w-[1400px]">
        <HealthBanner />
      </div>
      <main className="mx-auto mt-2 grid max-w-[1400px] gap-8 md:grid-cols-[320px_1fr]">
        <aside>
          <h2 className="mb-4 text-sm font-semibold">Job moi</h2>
          <JobForm
            onCreated={(id) => {
              setSelected(id);
              refresh();
            }}
          />
          <h2 className="mt-8 mb-3 text-sm font-semibold">Lan chay</h2>
          <JobList jobs={jobs} selected={selected} onSelect={setSelected} />
        </aside>
        <section>
          {selected ? (
            <JobDetail jobId={selected} onChanged={refresh} />
          ) : (
            <EmptyState title="Chua chon job nao" body="Chon mot lan chay o cot ben trai, hoac tao job moi." />
          )}
        </section>
      </main>
    </div>
  );
}
