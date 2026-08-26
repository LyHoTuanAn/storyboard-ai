import { useCallback, useEffect, useRef, useState } from "react";
import { listJobs } from "../api";
import type { Job } from "../types";

const POLL_MS = 4000;

export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const latestCall = useRef(0);

  const refresh = useCallback(async () => {
    const callId = ++latestCall.current;
    try {
      const result = await listJobs();
      // Bo qua ket qua neu mot lan goi refresh() moi hon da duoc phat ra
      // trong luc cho phan hoi nay - tranh du lieu cu de len du lieu moi
      // khi hai request chong cheo tra ve khong dung thu tu.
      if (callId === latestCall.current) {
        setJobs(result);
      }
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
