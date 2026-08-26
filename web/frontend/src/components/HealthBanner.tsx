import { useEffect, useState } from "react";
import { WarningIcon } from "@phosphor-icons/react";
import { getHealth } from "../api";
import type { Health } from "../types";

export function HealthBanner() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  if (!health) return null;

  const problems: string[] = [];
  if (!health.ffmpeg) problems.push("Khong tim thay ffmpeg. Buoc ghep video se hong.");
  if (!health.server_key) problems.push("Chua co GEMINI_API_KEY trong .env. Phai nhap key rieng o form.");

  if (problems.length === 0) return null;

  return (
    <div
      className="mb-4 flex items-start gap-2 px-4 py-3 text-sm"
      style={{
        border: "1px solid var(--st-interrupted)",
        borderRadius: "var(--radius)",
        color: "var(--st-interrupted)",
      }}
      role="status"
    >
      <WarningIcon size={18} />
      <div className="flex flex-col gap-1">
        {problems.map((problem) => (
          <span key={problem}>{problem}</span>
        ))}
      </div>
    </div>
  );
}
