import type { ReactNode } from "react";

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p className="text-xs" style={{ color: "var(--text-dim)" }}>
          {hint}
        </p>
      )}
      {error && (
        <p className="text-xs" style={{ color: "var(--st-failed)" }} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
