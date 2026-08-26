export type JobStatus =
  | "queued"
  | "running"
  | "done"
  | "failed"
  | "cancelled"
  | "interrupted"
  | "corrupt";

export interface JobParams {
  context: string;
  language: string;
  research_mode: "deep" | "web" | "none";
  use_internet_image_search: boolean;
  fast_mode: boolean;
  enable_veo: boolean;
  veo_direction_by_director: boolean;
}

export interface JobModels {
  MODEL_NAME: string | null;
  IMAGE_GEN_MODEL: string | null;
  TTS_MODEL: string | null;
}

export interface JobProgress {
  step: number | null;
  scene: number | null;
  total_scenes: number | null;
}

export interface Job {
  id: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  params: JobParams;
  models: JobModels;
  key_source: "server" | "user";
  pid: number | null;
  exit_code: number | null;
  result_video: string | null;
  error: string | null;
  progress: JobProgress;
}

export interface SceneArtifacts {
  scene: number;
  image: string | null;
  audio: string | null;
  video: string | null;
}

export interface Artifacts {
  scenes: SceneArtifacts[];
  final_video: string | null;
}

export interface Health {
  ffmpeg: boolean;
  server_key: boolean;
  running: number;
}
