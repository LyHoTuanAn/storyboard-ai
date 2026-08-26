import type { Job } from "../types";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";

export function JobList({
  jobs,
  selected,
  onSelect,
}: {
  jobs: Job[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  if (jobs.length === 0) {
    return <EmptyState title="Chua co lan chay nao" body="Dien chu de o form ben tren roi bam Chay." />;
  }

  return (
    <ul className="flex flex-col" style={{ borderTop: "1px solid var(--border)" }}>
      {jobs.map((job) => {
        const isSelected = job.id === selected;
        return (
          <li key={job.id} style={{ borderBottom: "1px solid var(--border)" }}>
            <button
              type="button"
              onClick={() => onSelect(job.id)}
              aria-current={isSelected ? "true" : undefined}
              className="flex w-full flex-col gap-1 py-3 pl-3 pr-3 text-left transition-colors"
              style={{
                background: isSelected ? "var(--surface)" : "transparent",
                borderLeft: `2px solid ${isSelected ? "var(--accent)" : "transparent"}`,
              }}
            >
              <span className="line-clamp-2 text-sm">{job.params?.context ?? job.id}</span>
              <span className="flex items-center gap-3">
                <StatusBadge status={job.status} />
                <span className="mono text-xs" style={{ color: "var(--text-dim)" }}>
                  {job.id.slice(2)}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
