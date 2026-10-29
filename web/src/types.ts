// Mirrors backend/unsaid/pipeline.py `result` (result.json).

export interface Word {
  text: string
  start: number
  end: number
}

export interface Interval {
  start: number
  end: number
}

export interface Gap extends Interval {
  id: string
}

export interface Segment extends Interval {
  id: string
  keyframes: number[]
}

export interface Moment {
  id: string
  t: number
  phrase: string
  sentence: string
  strength: 'strong' | 'weak'
  segment_id: string | null
}

export interface Resolution {
  moment_id: string
  refers_to_visual: boolean
  target: string
  unsaid: string
  confidence: number
}

export interface ClaimCheck {
  claim: string
  verdict: 'supported' | 'contradicted' | 'not_visible'
}

export interface Verification {
  claims: ClaimCheck[]
  identifies_person: boolean
  supported: boolean
  unsupported_claims: string[]
}

export interface Source {
  url: string
  title: string
  request_id: string
  used_for: string
}

export type Tier = 'auto' | 'review' | 'never'

export interface Cue {
  id: string
  gap_id: string | null
  start: number
  end: number
  text: string
  extended: boolean
  fact_ids: string[]
  moment_ids: string[]
  gate_failures: string[]
  gate_warnings: string[]
  repairs: number
  verification: Verification | null
  tier: Tier
  sources: Source[]
  edited?: boolean
  origin?: string
  corrected_from?: string
}

export interface Tip {
  moment_id: string
  t: number
  said: string
  suggestion: string
}

export interface VisualFact {
  id: string
  t: number
  segment_id: string
  fact: string
  importance: number
  already_spoken: boolean
  moment_id: string
}

export interface Bible {
  summary: string
  registry: { name: string; source: string }[]
  notation: string[]
  visual_facts: VisualFact[]
  cue_plan: { gap_id: string; fact_ids: string[]; intent: string }[]
  style_notes: string[]
}

export interface LedgerCall {
  stage: string
  role: string
  model: string
  model_label: string
  thinking: boolean
  prompt_tokens: number
  cached_tokens: number
  completion_tokens: number
  reasoning_tokens: number
  latency_ms: number
  ok: boolean
  error: string
  request_id: string
  cost_usd: number
  ultra_counterfactual_usd: number
}

export interface ModelRow {
  calls: number
  prompt_tokens: number
  cached_tokens: number
  completion_tokens: number
  cost_usd: number
}

export interface LedgerSummary {
  calls: number
  failed_calls: number
  total_usd: number
  ultra_only_usd: number
  by_model: Record<string, ModelRow>
  usd_per_video_minute?: number
  usd_per_accepted_cue?: number
}

export interface Metrics {
  duration_seconds: number
  cues: number
  inline_cues: number
  extended_cues: number
  tiers: Record<Tier, number>
  talk_over_seconds: number
  repairs: number
  gate_failures_after_repair: Record<string, number>
  pointing_moments: number
  pointing_moments_visual: number
  pointing_moments_covered: number
  flagged_by_check?: number
  corrected_after_check?: number
}

export interface RunResult {
  title: string
  video: { duration: number; width: number; height: number; fps: number }
  transcript: Word[]
  speech: Interval[]
  gaps: Gap[]
  segments: Segment[]
  moments: Moment[]
  resolutions: Record<string, Resolution>
  observations: Record<string, unknown>
  context: { names: string[]; sources: Source[] }
  bible: Bible
  cues: Cue[]
  tips: Tip[]
  metrics: Metrics
  ledger: { summary: LedgerSummary; calls: LedgerCall[] }
  timings: Record<string, number>
  failures?: { stage: string; segment: string; error: string }[]
  provider: string
}

export interface SampleInfo {
  id: string
  title: string
  credit: string
  license: string
  license_url: string
  source_url: string
  duration: number
  hero?: { start: number; end: number; moment_id?: string }
  run_seconds?: number
  provider?: string
}

export interface StageEvent {
  type: 'stage'
  stage: string
  label: string
  status: 'start' | 'done'
  detail?: string
  seconds?: number
  calls?: LedgerCall[]
  total_usd?: number
}

export type RunEvent =
  | StageEvent
  | { type: 'queued'; position: number }
  | { type: 'running' }
  | { type: 'tick'; stage: string; tokens: number }
  | { type: 'done'; metrics: Metrics; total_usd: number }
  | { type: 'finished'; status: 'done' | 'cancelled' | 'failed'; error?: string }

/** Where a result's media lives: a precomputed sample or a visitor's own run. */
export interface MediaBase {
  video: string
  poster?: string
  captions: string
  descriptions: string
  files: (name: string) => string
}
