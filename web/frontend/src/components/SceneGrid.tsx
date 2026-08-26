import { useEffect, useState } from "react";
import { getArtifacts, fileUrl } from "../api";
import type { Artifacts } from "../types";
import { SceneCard } from "./SceneCard";

function Skeleton() {
  return (
    <div
      className="aspect-video w-full"
      style={{ background: "var(--border)", borderRadius: "var(--radius)", opacity: 0.5 }}
      aria-hidden="true"
    />
  );
}

export function SceneGrid({ jobId, refreshKey }: { jobId: string; refreshKey: number }) {
  const [tree, setTree] = useState<Artifacts | null>(null);

  useEffect(() => {
    // Neu request nay hong (mang chap chon, server tam thoi loi...), giu
    // nguyen `tree` cu thay vi xoa trang - nguoi dung van dang xem anh/video
    // da tai duoc, khong nen bi mat chi vi mot lan lam moi that bai. Co
    // `ignore` de tranh ghi de bang ket qua cua mot request cu hon da bi
    // vuot mat boi mot lan goi moi hon (jobId hoac refreshKey doi lien tuc).
    let ignore = false;
    getArtifacts(jobId).then(
      (next) => {
        if (!ignore) setTree(next);
      },
      () => {
        // Bo qua loi: khong reset tree ve null.
      },
    );
    return () => {
      ignore = true;
    };
  }, [jobId, refreshKey]);

  if (!tree) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton />
        <Skeleton />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {tree.final_video && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">Video hoan chinh</h3>
          <video
            src={fileUrl(jobId, tree.final_video)}
            controls
            className="w-full"
            style={{ borderRadius: "var(--radius)", border: "1px solid var(--border)" }}
          />
        </div>
      )}

      {tree.scenes.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold">Tung scene</h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {tree.scenes.map((scene) => (
              <SceneCard key={scene.scene} jobId={jobId} scene={scene} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
