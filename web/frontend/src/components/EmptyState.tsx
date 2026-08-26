export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div
      className="flex flex-col items-start gap-2 px-5 py-10"
      style={{ border: "1px dashed var(--border)", borderRadius: "var(--radius)" }}
    >
      <p className="text-sm font-medium">{title}</p>
      <p className="text-sm" style={{ color: "var(--text-dim)" }}>
        {body}
      </p>
    </div>
  );
}
