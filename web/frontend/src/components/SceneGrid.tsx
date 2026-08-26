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

// Chua co scene nao xong (job vua bat dau) khong phai loi - dung mau/kieu
// trung lap voi cac khoi bao loi/canh bao trong JobDetail, chi noi ro day
// la trang thai binh thuong dang cho.
function EmptyPlaceholder() {
  return (
    <div
      className="px-4 py-6 text-center text-sm"
      style={{ border: "1px dashed var(--border)", borderRadius: "var(--radius)", color: "var(--text-dim)" }}
    >
      Cac scene se xuat hien o day khi duoc sinh ra.
    </div>
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
    // Cung so cot voi luoi da tai (sm:grid-cols-2 lg:grid-cols-3) - chi noi
    // dung thay doi khi tai xong, khong duoc doi ca so cot tren man hinh rong.
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Skeleton />
        <Skeleton />
      </div>
    );
  }

  // Job vua bat dau, chua scene nao xong: khong co gi de ve ca o final
  // video lan luoi scene. Day la trang thai binh thuong, khong phai loi.
  if (!tree.final_video && tree.scenes.length === 0) {
    return <EmptyPlaceholder />;
  }

  return (
    <div className="flex flex-col gap-6">
      {tree.final_video && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold">Video hoan chinh</h3>
          {/* Danh truoc khung 16:9 giong het cac o scene: <video> khong biet
              kich thuoc that cho toi khi metadata tai xong, day la video lon
              nhat trang nen neu khong danh truoc no se lam trang nhay manh
              nhat trong ca component. */}
          <div
            className="aspect-video w-full overflow-hidden"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
          >
            <video
              src={fileUrl(jobId, tree.final_video)}
              controls
              aria-label="Video hoan chinh"
              className="h-full w-full object-cover"
            />
          </div>
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
