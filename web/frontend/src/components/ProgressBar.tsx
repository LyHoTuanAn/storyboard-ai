import { PulseIcon } from "@phosphor-icons/react";
import type { SceneProgress } from "../hooks/useJobEvents";

export function ProgressBar({
  scene,
  step,
  stalled,
}: {
  scene: SceneProgress | null;
  step: { n: number; label: string } | null;
  stalled: boolean;
}) {
  const percent = scene ? Math.round((scene.current / scene.total) * 100) : null;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm">{step ? step.label : "Dang khoi dong..."}</span>
        <span className="mono text-xs" style={{ color: "var(--text-dim)" }}>
          {scene ? `scene ${scene.current}/${scene.total}` : ""}
        </span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden"
        style={{ background: "var(--border)", borderRadius: "var(--radius)" }}
        role="progressbar"
        aria-valuenow={percent ?? undefined}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full transition-[width] duration-500"
          style={{
            width: percent === null ? "100%" : `${percent}%`,
            background: "var(--accent)",
            opacity: percent === null ? 0.35 : 1,
          }}
        />
      </div>
      {/* Job co the im lang that su hon 10 phut trong luc sinh video hoac
          nghien cuu sau. `stalled` chi bao server da dong response sau
          600s khong co log moi - ket noi van mo va se tu phuc hoi, day
          khong phai loi nen khong dung mau trang thai loi/canh bao va
          khong dung role="alert". Dong nay tu bien mat ngay khi co su
          kien moi vi no chi phu thuoc vao prop `stalled`. */}
      {stalled && (
        <p
          className="flex items-center gap-1.5 text-xs"
          style={{ color: "var(--text-dim)" }}
          role="status"
        >
          <PulseIcon size={14} aria-hidden="true" />
          Chua co cap nhat moi mot luc. Ket noi van dang lang nghe va se tu cap nhat.
        </p>
      )}
    </div>
  );
}
