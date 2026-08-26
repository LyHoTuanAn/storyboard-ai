import { useCallback, useEffect, useState } from "react";
import { listJobs } from "../api";
import type { Job } from "../types";

const POLL_MS = 4000;

export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);

  const refresh = useCallback(async () => {
    try {
      setJobs(await listJobs());
    } catch {
      // giu danh sach cu neu goi that bai
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  return { jobs, refresh };
}
