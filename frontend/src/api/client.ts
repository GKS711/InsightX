import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v5",
  timeout: 30_000,
});

// 統一錯誤型別
export interface ApiError {
  detail?: string;
  message?: string;
  status?: number;
}

// ─────────────────────────────────────────────────────────────────
// Type-safe payloads (mirrors src/schemas.py on the backend)
// ─────────────────────────────────────────────────────────────────

export interface Workspace {
  id: number;
  owner_user_id: number;
  name: string;
  created_at: string;
}

export interface Store {
  id: number;
  workspace_id: number;
  name: string;
  address: string | null;
  primary_url: string | null;
  platform: "google" | "youtube";
  created_at: string;
}

export interface ReviewSource {
  id: number;
  store_id: number;
  source_type: "google_maps" | "youtube";
  external_url: string;
  last_scraped_at: string | null;
  total_reviews_estimated: number | null;
}

export interface ScrapeJob {
  id: number;
  source_id: number;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  started_at: string | null;
  finished_at: string | null;
  error_class: string | null;
  error_message: string | null;
  attempt_number: number;
  reviews_fetched_count: number;
  pagination_truncated: boolean;
}

export interface AnalysisRun {
  id: number;
  store_id: number;
  ai_function: string;
  prompt_version: string;
  model_id: string;
  output_json: Record<string, unknown> | null;
  tokens_used: number | null;
  cost_cents: number | null;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  error_class: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface Review {
  id: number;
  source_id: number;
  scrape_job_id: number | null;
  author: string | null;
  rating: number | null;
  text: string;
  published_at: string | null;
}

export type AiFunction =
  | "analyze"
  | "swot"
  | "reply"
  | "analyze_issue"
  | "marketing"
  | "weekly_plan"
  | "training_script"
  | "internal_email"
  | "chat";
