import { WarningIcon } from "@phosphor-icons/react";
import { fileUrl } from "../api";
import type { SceneArtifacts } from "../types";

export function SceneCard({ jobId, scene }: { jobId: string; scene: SceneArtifacts }) {
  return (
    <figure className="flex flex-col gap-2">
      <div
        className="aspect-video w-full overflow-hidden"
        style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
      >
        {scene.video ? (
          <video
            src={fileUrl(jobId, scene.video)}
            controls
            aria-label={`Video scene ${scene.scene}`}
            className="h-full w-full object-cover"
          />
        ) : scene.image ? (
          <img
            src={fileUrl(jobId, scene.image)}
            alt={`Scene ${scene.scene}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div
            className="flex h-full w-full items-center justify-center gap-2 text-xs"
            style={{ color: "var(--st-interrupted)" }}
          >
            <WarningIcon size={16} />
            Khong co anh
          </div>
        )}
      </div>
      <figcaption className="flex items-center justify-between text-xs">
        <span className="mono" style={{ color: "var(--text-dim)" }}>
          scene {scene.scene}
        </span>
        {scene.audio && (
          <audio
            src={fileUrl(jobId, scene.audio)}
            controls
            aria-label={`Am thanh scene ${scene.scene}`}
            className="h-8"
          />
        )}
      </figcaption>
    </figure>
  );
}
