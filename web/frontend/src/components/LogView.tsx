import { useEffect, useRef, useState } from "react";

export function LogView({ lines }: { lines: string[] }) {
  const [follow, setFollow] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (follow) endRef.current?.scrollIntoView({ block: "end" });
  }, [lines, follow]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Nhat ky</h3>
        <label className="flex items-center gap-2 text-xs" htmlFor="follow">
          <input
            id="follow"
            type="checkbox"
            checked={follow}
            onChange={(event) => setFollow(event.target.checked)}
          />
          Tu cuon
        </label>
      </div>
      <div
        className="mono h-72 overflow-auto px-3 py-2 text-xs leading-relaxed"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          color: "var(--text-dim)",
        }}
      >
        {lines.map((line, index) => (
          <div key={index} className="whitespace-pre-wrap">
            {line}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
