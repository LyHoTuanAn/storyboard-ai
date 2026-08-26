import { useCallback, useEffect, useRef, useState } from "react";
import { StopIcon, WarningIcon } from "@phosphor-icons/react";
import { cancelJob, getJob } from "../api";
import { useJobEvents } from "../hooks/useJobEvents";
import type { Job } from "../types";
import { LogView } from "./LogView";
import { ProgressBar } from "./ProgressBar";
import { StatusBadge } from "./StatusBadge";

// "corrupt" (job.json khong doc duoc - xem web/jobs.py:read_job) duoc coi
// la mot trang thai khong con hoat dong o day, GIONG NHU cac trang thai
// terminal thuc su: khong co gi de huy, khong co tien trinh de theo doi.
// Luu y day la mot khai niem rieng cua frontend, khac voi TERMINAL ben
// backend (web/jobs.py) - backend co mot nhanh rieng cho "corrupt" vi no
// can tu choi CHUYEN TRANG THAI (set_status/spawn), con o day chi can biet
// "co dang chay khong" de an/hien Cancel va ProgressBar.
const TERMINAL = ["done", "failed", "cancelled", "interrupted", "corrupt"];

// Huy job la hanh dong pha huy va khong the hoan tac: job dang chay co the
// da tieu ton quota API that (goi model, sinh anh/video...). Vi vay nut Huy
// khong bam mot phat la thi hanh ngay - lan bam dau tien chi chuyen sang
// trang thai "cho xac nhan", phai bam lan nua trong CONFIRM_TIMEOUT_MS thi
// lenh huy moi thuc su gui di. Nguoi dung cung co the bam "Thoi" de thoat
// khoi trang thai cho xac nhan bat cu luc nao.
const CONFIRM_TIMEOUT_MS = 4000;

export function JobDetail({ jobId, onChanged }: { jobId: string; onChanged: () => void }) {
  const [job, setJob] = useState<Job | null>(null);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const confirmTimer = useRef<number | null>(null);
  const { lines, step, scene, warnings, status, stalled } = useJobEvents(jobId);

  const reload = useCallback(async () => {
    setJob(await getJob(jobId));
  }, [jobId]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    if (status) {
      reload();
      onChanged();
    }
  }, [status, reload, onChanged]);

  // Chuyen sang job khac thi bo trang thai xac nhan huy cua job truoc do.
  useEffect(() => {
    setConfirmingCancel(false);
    setCancelling(false);
    return () => {
      if (confirmTimer.current !== null) window.clearTimeout(confirmTimer.current);
    };
  }, [jobId]);

  const clearConfirm = useCallback(() => {
    if (confirmTimer.current !== null) window.clearTimeout(confirmTimer.current);
    confirmTimer.current = null;
    setConfirmingCancel(false);
  }, []);

  const requestCancel = useCallback(() => {
    if (!confirmingCancel) {
      setConfirmingCancel(true);
      confirmTimer.current = window.setTimeout(() => {
        confirmTimer.current = null;
        setConfirmingCancel(false);
      }, CONFIRM_TIMEOUT_MS);
      return;
    }
    if (confirmTimer.current !== null) window.clearTimeout(confirmTimer.current);
    confirmTimer.current = null;
    setCancelling(true);
    cancelJob(jobId)
      .then(() => reload())
      .then(() => onChanged())
      .finally(() => {
        setCancelling(false);
        setConfirmingCancel(false);
      });
  }, [confirmingCancel, jobId, reload, onChanged]);

  if (!job) return null;

  // Mot job "corrupt" chi co { id, status } - moi truong khac (params,
  // error, exit_code, progress...) co the vang mat. running=false cho no
  // (qua TERMINAL o tren) da tu dong an nut Huy va ProgressBar; cac truy
  // cap truong con lai duoi day deu phai qua optional chaining/dieu kien
  // rieng, khong duoc gia dinh job co day du du lieu.
  const corrupt = job.status === "corrupt";
  const running = !TERMINAL.includes(job.status);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          {/* job.params co the vang mat (job "corrupt") - cung mau bao ve
              bang optional chaining ma JobList.tsx da dung. */}
          <h2 className="text-base font-semibold">{job.params?.context ?? job.id}</h2>
          <div className="flex items-center gap-3">
            <StatusBadge status={job.status} />
            <span className="mono text-xs" style={{ color: "var(--text-dim)" }}>
              {job.id}
            </span>
          </div>
        </div>
        {running && (
          <div className="flex items-center gap-2">
            {confirmingCancel && (
              <button
                type="button"
                onClick={clearConfirm}
                className="px-3 py-2 text-sm"
                style={{ color: "var(--text-dim)" }}
              >
                Thoi
              </button>
            )}
            <button
              type="button"
              onClick={requestCancel}
              disabled={cancelling}
              aria-label={confirmingCancel ? "Bam lan nua de xac nhan huy job" : "Huy job"}
              className="flex items-center gap-2 px-3 py-2 text-sm transition-transform active:scale-[0.98]"
              style={{
                border: "1px solid var(--st-failed)",
                color: "var(--st-failed)",
                borderRadius: "var(--radius)",
                opacity: cancelling ? 0.6 : 1,
              }}
            >
              <StopIcon size={16} />
              {cancelling ? "Dang huy..." : confirmingCancel ? "Xac nhan huy?" : "Huy"}
            </button>
          </div>
        )}
      </div>

      {running && <ProgressBar scene={scene} step={step} stalled={stalled} />}

      {corrupt && (
        <div
          className="flex items-center gap-2 px-4 py-3 text-sm"
          style={{
            border: "1px solid var(--st-failed)",
            borderRadius: "var(--radius)",
            color: "var(--st-failed)",
          }}
          role="alert"
        >
          <WarningIcon size={16} />
          <span>
            Khong doc duoc du lieu cua job nay (file job.json bi hong). Khong
            the xem chi tiet, nhat ky, hay huy job tu day.
          </span>
        </div>
      )}

      {job.status === "failed" && job.error && (
        <div
          className="flex flex-col gap-2 px-4 py-3 text-sm"
          style={{
            border: "1px solid var(--st-failed)",
            borderRadius: "var(--radius)",
            color: "var(--st-failed)",
          }}
          role="alert"
        >
          <span className="flex items-center gap-2 font-medium">
            <WarningIcon size={16} />
            Job hong (ma thoat {job.exit_code})
          </span>
          <p className="mono text-xs whitespace-pre-wrap">{job.error}</p>
        </div>
      )}

      {warnings.length > 0 && (
        <ul className="flex flex-col gap-1 text-xs" style={{ color: "var(--st-interrupted)" }}>
          {warnings.map((warning, index) => (
            <li key={index}>
              Scene {warning.scene} bi bo qua: {warning.message}
            </li>
          ))}
        </ul>
      )}

      {/* Khong co job.json doc duoc thi khong co gi that de theo doi -
          khong hien mot khung nhat ky rong, gay hieu lam la con dang co du
          lieu song. */}
      {!corrupt && <LogView lines={lines} />}
    </div>
  );
}
