import type { MediaBase, RunResult, SampleInfo } from './types'

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

export interface Health {
  ok: boolean
  provider: string
  demo_mode: 'live' | 'recorded'
  models: Record<string, string>
  stages: { key: string; label: string; detail: string }[]
}

export const api = {
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
}

export function sampleMedia(id: string): MediaBase {
  const base = `/media/samples/${encodeURIComponent(id)}`
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
