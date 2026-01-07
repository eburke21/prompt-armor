/**
 * Typed API client for the PromptArmor backend.
 *
 * Uses fetch (no axios) — keeps it simple and avoids an extra dependency.
 * Each function returns typed data matching the backend Pydantic models.
 */

import type {
  AttackListResponse,
  AttackPromptDetail,
  EvalRun,
  EvalRunCreate,
  EvalRunResponse,
  PaginatedResults,
  SystemPrompt,
  TaxonomyResponse,
} from "./types";

const API_BASE = "/api/v1";

// ---------------------------------------------------------------------------
// Generic fetcher
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Dataset & Taxonomy
// ---------------------------------------------------------------------------

export async function getTaxonomy(): Promise<TaxonomyResponse> {
  return apiFetch<TaxonomyResponse>("/taxonomy");
}

export interface GetAttacksParams {
  technique?: string;
  source?: string;
  difficulty_min?: number;
  difficulty_max?: number;
  is_injection?: boolean;
  language?: string;
  limit?: number;
  offset?: number;
}

export async function getAttacks(
  params: GetAttacksParams = {}
): Promise<AttackListResponse> {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      qs.set(key, String(value));
    }
  }
  const query = qs.toString();
  return apiFetch<AttackListResponse>(`/attacks${query ? `?${query}` : ""}`);
}

export async function getAttackById(
  id: string
): Promise<AttackPromptDetail> {
  return apiFetch<AttackPromptDetail>(`/attacks/${id}`);
}

export interface GetRandomAttacksParams {
  count?: number;
  technique?: string;
  difficulty_min?: number;
  difficulty_max?: number;
}

export async function getRandomAttacks(
  params: GetRandomAttacksParams = {}
): Promise<AttackPromptDetail[]> {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      qs.set(key, String(value));
    }
  }
  const query = qs.toString();
  return apiFetch<AttackPromptDetail[]>(
    `/attacks/random${query ? `?${query}` : ""}`
  );
}

// ---------------------------------------------------------------------------
// System prompts
// ---------------------------------------------------------------------------

export interface GetSystemPromptsParams {
  source?: string;
  category?: string;
}

export async function getSystemPrompts(
  params: GetSystemPromptsParams = {}
): Promise<SystemPrompt[]> {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      qs.set(key, String(value));
    }
  }
  const query = qs.toString();
  return apiFetch<SystemPrompt[]>(
    `/system-prompts${query ? `?${query}` : ""}`
  );
}

// ---------------------------------------------------------------------------
// Eval runs
// ---------------------------------------------------------------------------

export async function startEvalRun(
  config: EvalRunCreate
): Promise<EvalRunResponse> {
  return apiFetch<EvalRunResponse>("/eval/run", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function getEvalRun(id: string): Promise<EvalRun> {
  return apiFetch<EvalRun>(`/eval/run/${id}`);
}

export async function getEvalResults(
  runId: string,
  params: { limit?: number; offset?: number } = {}
): Promise<PaginatedResults> {
  const qs = new URLSearchParams();
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.offset) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return apiFetch<PaginatedResults>(
    `/eval/run/${runId}/results${query ? `?${query}` : ""}`
  );
}
