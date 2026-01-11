// ---------------------------------------------------------------------------
// Types matching the backend Pydantic models
// ---------------------------------------------------------------------------

/** Technique info from /api/v1/taxonomy */
export interface TechniqueInfo {
  id: string;
  name: string;
  description: string;
  example_count: number;
  difficulty_distribution: Record<string, number>;
}

/** Dataset info from /api/v1/taxonomy */
export interface DatasetInfo {
  id: string;
  name: string;
  count: number;
  license: string;
}

/** Full taxonomy response */
export interface TaxonomyResponse {
  techniques: TechniqueInfo[];
  total_prompts: number;
  total_injections: number;
  total_benign: number;
  datasets: DatasetInfo[];
}

/** A single attack prompt */
export interface AttackPrompt {
  id: string;
  source_dataset: string;
  is_injection: boolean;
  prompt_text: string;
  language: string;
  difficulty_estimate: number | null;
  character_count: number;
}

/** Attack prompt with technique details */
export interface AttackPromptDetail extends AttackPrompt {
  techniques: PromptTechnique[];
  original_label: string;
}

/** Technique tag on a prompt */
export interface PromptTechnique {
  technique: string;
  confidence: number;
  classified_by: string;
}

/** Paginated attack list response */
export interface AttackListResponse {
  attacks: AttackPromptDetail[];
  total: number;
  limit: number;
  offset: number;
}

/** System prompt */
export interface SystemPrompt {
  id: string;
  source: string;
  name: string | null;
  prompt_text: string;
  category: string | null;
}

// ---------------------------------------------------------------------------
// Defense configuration types
// ---------------------------------------------------------------------------

export interface KeywordBlocklistConfig {
  type: "keyword_blocklist";
  enabled: boolean;
  keywords: string[];
}

export interface OpenAIModerationConfig {
  type: "openai_moderation";
  enabled: boolean;
  threshold: number;
  categories: string[];
}

export type InputFilter = KeywordBlocklistConfig | OpenAIModerationConfig;

export interface SecretLeakDetectorConfig {
  type: "secret_leak_detector";
  enabled: boolean;
  secrets: string[];
  patterns: string[];
}

export type OutputFilter = SecretLeakDetectorConfig;

export interface DefenseConfig {
  system_prompt: string;
  input_filters: InputFilter[];
  output_filters: OutputFilter[];
}

export interface AttackSetConfig {
  techniques: string[];
  difficulty_range: [number, number];
  count: number;
  include_benign: boolean;
  benign_ratio: number;
}

export interface EvalRunCreate {
  defense_config: DefenseConfig;
  attack_set: AttackSetConfig;
}

// ---------------------------------------------------------------------------
// Eval run types
// ---------------------------------------------------------------------------

export interface EvalRunResponse {
  eval_run_id: string;
  status: string;
  total_prompts: number;
  stream_url: string;
}

export interface TechniqueScore {
  total: number;
  blocked: number;
  rate: number;
}

export interface LayerScore {
  blocked: number;
  rate: number;
}

export interface DifficultyScore {
  total: number;
  blocked: number;
  rate: number;
}

export interface Scorecard {
  eval_run_id: string;
  total_attacks: number;
  total_benign: number;
  attack_block_rate: number;
  false_positive_rate: number;
  by_technique: Record<string, TechniqueScore>;
  by_layer: Record<string, LayerScore>;
  by_difficulty: Record<string, DifficultyScore>;
}

export interface EvalRun {
  id: string;
  status: string;
  defense_config: DefenseConfig;
  attack_set_config: AttackSetConfig;
  total_prompts: number;
  completed_prompts: number;
  summary_stats: Scorecard | null;
  created_at: string;
}

export interface EvalResultItem {
  id: string;
  prompt_id: string;
  prompt_text: string;
  source_dataset: string;
  difficulty_estimate: number | null;
  is_injection: boolean;
  input_filter_blocked: boolean;
  input_filter_type: string | null;
  input_filter_score: number | null;
  llm_response: string | null;
  llm_latency_ms: number | null;
  output_filter_blocked: boolean;
  output_filter_type: string | null;
  injection_succeeded: boolean | null;
  blocked_by: string | null;
  semantic_eval_score: number | null;
}

export interface PaginatedResults {
  results: EvalResultItem[];
  total: number;
  limit: number;
  offset: number;
}

// ---------------------------------------------------------------------------
// SSE event types
// ---------------------------------------------------------------------------

export interface ProgressEvent {
  completed: number;
  total: number;
  current_prompt_id: string;
}

export interface ResultEvent {
  prompt_id: string;
  prompt_text: string;
  is_injection: boolean;
  blocked: boolean;
  blocked_by: string | null;
  input_filter_blocked: boolean;
  input_filter_type: string | null;
  output_filter_blocked: boolean;
  output_filter_type: string | null;
  injection_succeeded: boolean | null;
  llm_latency_ms: number | null;
  techniques: string[];
  difficulty: number;
}

export interface CompleteEvent {
  eval_run_id: string;
  scorecard: Scorecard;
}

export interface ErrorEvent {
  message: string;
  prompt_id?: string;
}

// ---------------------------------------------------------------------------
// Comparison types
// ---------------------------------------------------------------------------

export interface ComparisonCreate {
  defense_configs: DefenseConfig[];
  attack_set: AttackSetConfig;
}

export interface ComparisonResponse {
  comparison_id: string;
  eval_run_ids: string[];
  total_prompts: number;
  stream_url: string;
}

export interface ComparisonRun {
  config_index: number;
  id: string;
  status: string;
  defense_config: DefenseConfig;
  total_prompts: number;
  completed_prompts: number;
  summary_stats?: Scorecard;
}

export interface ComparisonStatus {
  comparison_id: string;
  status: string;
  runs: ComparisonRun[];
}

/** SSE result event extended with config_index for comparisons */
export interface ComparisonResultEvent extends ResultEvent {
  config_index: number;
}

/** Emitted when one config in a comparison finishes */
export interface ConfigCompleteEvent {
  config_index: number;
  eval_run_id: string;
  scorecard: Scorecard;
}

/** Emitted when all configs in a comparison have finished */
export interface AllCompleteEvent {
  comparison_id: string;
  scorecards: Scorecard[];
}

// ---------------------------------------------------------------------------
// Report types
// ---------------------------------------------------------------------------

export interface ReportGenerateRequest {
  eval_run_ids: string[];
}

export interface ReportGenerateResponse {
  markdown: string;
  eval_run_ids: string[];
  model_used: string;
}
