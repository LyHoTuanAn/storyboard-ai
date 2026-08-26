import { useEffect, useState } from "react";
import type { JobStatus } from "../types";

export interface SceneProgress {
  current: number;
  total: number;
}

export interface JobWarning {
  scene: number;
  message: string;
}

interface StepPayload {
  n: number;
  label: string;
}

interface StatusPayload {
  status: JobStatus;
  stalled?: boolean;
}

const MAX_LINES = 2000;

// Trang thai duoc coi la "ket thuc that su" - khi status event mang mot
// trong nhung gia tri nay, job da xong va se khong co su kien nao khac
// nua. Bat ky status nao khac (bao gom trang thai "stalled" ma server
// gui khi im lang qua 600s trong luc job VAN dang running) khong duoc
// dong ket noi hay ghi de vao state status.
//
// "corrupt" PHAI co mat o day: phia server, web/events.py ket thuc luong
// ngay lap tuc cho trang thai nay (END_STATUSES). Neu client khong coi no
// la ket thuc, EventSource se tu ket noi lai sau moi lan server dong -
// khoang 3 giay mot lan, mai mai - va giao dien hien goi y "dang im lang"
// thay vi trang thai loi file. Hai tap hop nay phai luon khop nhau.
const TERMINAL_STATUSES: readonly JobStatus[] = [
  "done",
  "failed",
  "cancelled",
  "interrupted",
  "corrupt",
];

function parsePayload<T>(event: Event): T | null {
  const raw = (event as MessageEvent).data;
  try {
    return JSON.parse(raw) as T;
  } catch {
    // Mot frame SSE hong (JSON khong hop le) khong duoc phep lam chet
    // stream - bo qua frame do va cho frame ke tiep.
    return null;
  }
}

/**
 * @param enabled Mo luong hay khong. Nguoi goi dat `false` khi da biet
 * khong co gi de nghe (job "corrupt": server se dong luong ngay, va
 * JobDetail cung an luon khung nhat ky) - mo roi dong ngay chi tao ra mot
 * vong ket noi thua.
 */
export function useJobEvents(jobId: string | null, enabled = true) {
  const [lines, setLines] = useState<string[]>([]);
  const [step, setStep] = useState<StepPayload | null>(null);
  const [scene, setScene] = useState<SceneProgress | null>(null);
  const [warnings, setWarnings] = useState<JobWarning[]>([]);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [stalled, setStalled] = useState(false);

  useEffect(() => {
    setLines([]);
    setStep(null);
    setScene(null);
    setWarnings([]);
    setStatus(null);
    setStalled(false);

    if (!jobId || !enabled) return;

    const source = new EventSource(`/api/jobs/${jobId}/events`);

    source.addEventListener("log", (event) => {
      setStalled(false);
      const payload = parsePayload<{ line: string }>(event);
      if (!payload) return;
      setLines((prev) => {
        const next = [...prev, payload.line];
        return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
      });
    });
    source.addEventListener("step", (event) => {
      setStalled(false);
      const payload = parsePayload<StepPayload>(event);
      if (payload) setStep(payload);
    });
    source.addEventListener("scene", (event) => {
      setStalled(false);
      const payload = parsePayload<SceneProgress>(event);
      if (payload) setScene(payload);
    });
    source.addEventListener("warning", (event) => {
      setStalled(false);
      const payload = parsePayload<JobWarning>(event);
      if (payload) setWarnings((prev) => [...prev, payload]);
    });
    source.addEventListener("status", (event) => {
      setStalled(false);
      const payload = parsePayload<StatusPayload>(event);
      if (!payload) return;

      if (!TERMINAL_STATUSES.includes(payload.status)) {
        // Server bao im lang (stalled) trong khi job van dang chay - KHONG
        // dong ket noi va KHONG ghi trang thai nay vao state, neu khong
        // downstream se tuong job da ket thuc. De ket noi mo: khi server
        // ket thuc response, EventSource tu dong ket noi lai va gui lai
        // Last-Event-ID, luong se tiep tuc dung cho o cho no dung.
        setStalled(true);
        return;
      }

      setStatus(payload.status);
      source.close();
    });

    return () => {
      source.close();
    };
  }, [jobId, enabled]);

  return { lines, step, scene, warnings, status, stalled };
}
