import type { Artifacts, Health, Job, JobModels, JobParams } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.error?.message ?? `Loi ${resp.status}`);
  }
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

export function createJob(payload: {
  params: JobParams;
  models?: Partial<JobModels>;
  api_key?: string;
}): Promise<{ id: string }> {
  return request("/api/jobs", { method: "POST", body: JSON.stringify(payload) });
}

export const listJobs = (): Promise<Job[]> => request("/api/jobs");
export const getJob = (id: string): Promise<Job> => request(`/api/jobs/${id}`);
export const cancelJob = (id: string): Promise<Job> =>
  request(`/api/jobs/${id}/cancel`, { method: "POST" });
export const deleteJob = (id: string): Promise<void> =>
  request(`/api/jobs/${id}`, { method: "DELETE" });
export const getArtifacts = (id: string): Promise<Artifacts> =>
  request(`/api/jobs/${id}/artifacts`);
export const getHealth = (): Promise<Health> => request("/api/health");

export const fileUrl = (id: string, path: string): string =>
  `/api/jobs/${id}/file?path=${encodeURIComponent(path)}`;
