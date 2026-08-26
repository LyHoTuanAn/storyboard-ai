import type { JobStatus } from "../types";

const LABEL: Record<JobStatus, string> = {
  queued: "Cho luot",
  running: "Dang chay",
  done: "Xong",
  failed: "Hong",
  cancelled: "Da huy",
  interrupted: "Bi ngat",
  corrupt: "Loi file",
};

const TOKEN: Record<JobStatus, string> = {
  queued: "var(--st-queued)",
  running: "var(--st-running)",
  done: "var(--st-done)",
  failed: "var(--st-failed)",
  cancelled: "var(--st-cancelled)",
  interrupted: "var(--st-interrupted)",
  corrupt: "var(--st-failed)",
};

// Nhan luon dung mau van ban chuan (--text) thay vi TOKEN[status]: hai token
// --st-queued/--st-cancelled khong dat AA 4.5:1 tren nen --bg/--surface khi
// dung lam mau chu (chi ~3.4:1). Cham mau van dung TOKEN[status] de mang
// trang thai that; van ban luon doc duoc bat ke trang thai nao.
export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs" style={{ color: "var(--text)" }}>
      <span
        aria-hidden="true"
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ background: TOKEN[status] }}
      />
      {LABEL[status]}
    </span>
  );
}
