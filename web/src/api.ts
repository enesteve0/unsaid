import type { MediaBase, RunResult, SampleInfo } from './types'

/** The static demo (GitHub Pages) has no server: examples and the evaluation are files, and nothing runs live. */
export const STATIC = import.meta.env.VITE_STATIC === '1'
const BASE = import.meta.env.BASE_URL
const file = (path: string) => BASE + path

const NO_SERVER = () => Promise.reject(new ApiError('This demo is a static site: describing a new clip needs the full app.', 503))
const STATIC_HEALTH: Health = { ok: true, provider: 'tokenfactory', host: '', live_status: 'static', demo_mode: 'recorded', models: {}, stages: [] }

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { credentials: 'same-origin', ...init })
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(message, res.status)
  }
  return res.json() as Promise<T>
}

export interface Backlog {
  available: boolean
  finished_at?: string
  seconds?: number
  spent_usd?: number
  budget_usd?: number
  ready?: number
  need_review?: number
  lectures?: { id: string; title: string; status: string; cues?: number; auto?: number; review?: number; cost_usd?: number; reason?: string }[]
}

export interface Health {
  ok: boolean
  provider: string
  host?: string
  live_status?: 'live' | 'paused' | 'ended' | 'judges_only' | 'static'
  demo_mode: 'live' | 'recorded'
  models: Record<string, string>
  stages: { key: string; label: string; detail: string }[]
}

const live = {
  health: () => request<Health>('/api/health'),
  samples: () => request<SampleInfo[]>('/api/samples'),
  sampleResult: (id: string) => request<RunResult>(`/api/samples/${encodeURIComponent(id)}/result`),
  runResult: (id: string) => request<RunResult>(`/api/runs/${encodeURIComponent(id)}/result`),
  runStatus: (id: string) =>
    request<{ id: string; title: string; status: string; position: number; error: string }>(
      `/api/runs/${encodeURIComponent(id)}`,
    ),
  myRuns: () => request<{ id: string; title: string; status: string; created: number; cost_usd: number }[]>('/api/runs'),
  createRun: (form: FormData) => request<{ run_id: string; position: number; lane: string }>('/api/runs', { method: 'POST', body: form }),
  cancelRun: (id: string) => request<{ cancelled: boolean }>(`/api/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  judge: (code: string) =>
    request<{ lane: string }>('/api/judge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    }),
  editCue: (runId: string, cueId: string, text: string) =>
    request<{ passed: boolean; failures: string[]; warnings: string[]; estimated_seconds: number }>(
      `/api/runs/${encodeURIComponent(runId)}/cues/${encodeURIComponent(cueId)}`,
      { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) },
    ),
  evaluation: () => request<Record<string, unknown>>('/api/eval'),
  backlog: () => request<Backlog>('/api/backlog'),
}

export const api: typeof live = STATIC
  ? {
      ...live,
      health: () => Promise.resolve(STATIC_HEALTH),
      samples: () => request<SampleInfo[]>(file('media/samples/manifest.json')),
      sampleResult: (id: string) => request<RunResult>(file(`media/samples/${encodeURIComponent(id)}/result.json`)),
      evaluation: () => request<Record<string, unknown>>(file('eval/report.json')),
      backlog: () => Promise.resolve({ available: false }),
      runResult: NO_SERVER,
      runStatus: NO_SERVER,
      myRuns: NO_SERVER,
      createRun: NO_SERVER,
      cancelRun: NO_SERVER,
      judge: NO_SERVER,
      editCue: NO_SERVER,
    }
  : live

export function sampleMedia(id: string): MediaBase {
  const base = `${BASE}media/samples/${encodeURIComponent(id)}`
  return {
    video: `${base}/video.mp4`,
    poster: `${base}/poster.jpg`,
    captions: `${base}/captions.vtt`,
    descriptions: `${base}/descriptions.vtt`,
    files: (name) => `${base}/${name}`,
  }
}

export function runMedia(id: string): MediaBase {
  const base = `/api/runs/${encodeURIComponent(id)}`
  return {
    video: `${base}/video`,
    captions: `${base}/files/captions.vtt`,
    descriptions: `${base}/files/descriptions.vtt`,
    files: (name) => `${base}/files/${name}`,
  }
}

export const fmtTime = (s: number) => {
  const m = Math.floor(s / 60)
  const sec = s - m * 60
  return `${m}:${sec.toFixed(1).padStart(4, '0')}`
}

export const fmtUsd = (usd: number) => (usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(3)}`)
