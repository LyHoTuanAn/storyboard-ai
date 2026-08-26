import { useEffect, useRef, useState } from "react";
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
}

const MAX_LINES = 2000;

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

export function useJobEvents(jobId: string | null) {
  const [lines, setLines] = useState<string[]>([]);
  const [step, setStep] = useState<StepPayload | null>(null);
  const [scene, setScene] = useState<SceneProgress | null>(null);
  const [warnings, setWarnings] = useState<JobWarning[]>([]);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    setLines([]);
    setStep(null);
    setScene(null);
    setWarnings([]);
    setStatus(null);

    if (!jobId) return;

    const source = new EventSource(`/api/jobs/${jobId}/events`);
    sourceRef.current = source;

    source.addEventListener("log", (event) => {
      const payload = parsePayload<{ line: string }>(event);
      if (!payload) return;
      setLines((prev) => {
        const next = [...prev, payload.line];
        return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
      });
    });
    source.addEventListener("step", (event) => {
      const payload = parsePayload<StepPayload>(event);
      if (payload) setStep(payload);
    });
    source.addEventListener("scene", (event) => {
      const payload = parsePayload<SceneProgress>(event);
      if (payload) setScene(payload);
    });
    source.addEventListener("warning", (event) => {
      const payload = parsePayload<JobWarning>(event);
      if (payload) setWarnings((prev) => [...prev, payload]);
    });
    source.addEventListener("status", (event) => {
      const payload = parsePayload<StatusPayload>(event);
      if (payload) setStatus(payload.status);
      source.close();
    });

    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, [jobId]);

  return { lines, step, scene, warnings, status };
}
