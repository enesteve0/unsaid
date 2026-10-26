import { useEffect, useState } from 'react'
import { api, fmtUsd } from '../api'
import { STAGES } from '../lib/stages'
import type { RunEvent } from '../types'

type StageState = { state: 'waiting' | 'running' | 'done'; seconds?: number; calls?: number; tokens?: number }

interface Props {
  runId: string
  onFinished: (status: 'done' | 'cancelled' | 'failed', error?: string) => void
}

export function RunProgress({ runId, onFinished }: Props) {
  const [position, setPosition] = useState<number | null>(null)
  const [stages, setStages] = useState<Record<string, StageState>>({})
  const [total, setTotal] = useState(0)
  const [status, setStatus] = useState('Queued')
  const [stopping, setStopping] = useState(false)

  useEffect(() => {
    const source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`)
    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as RunEvent
      if (event.type === 'queued') {
        setPosition(event.position)
        setStatus(event.position > 1 ? `In the queue: ${event.position - 1} ahead of you` : 'Starting next')
      } else if (event.type === 'running') {
        setPosition(null)
        setStatus('Describing')
      } else if (event.type === 'stage') {
        setStages((prev) => ({
          ...prev,
          [event.stage]:
            event.status === 'start'
              ? { state: 'running' }
              : { state: 'done', seconds: event.seconds, calls: event.calls?.length ?? 0 },
        }))
        if (event.total_usd !== undefined) setTotal(event.total_usd)
        if (event.status === 'start') setStatus(`${event.label}: ${event.detail ?? ''}`)
      } else if (event.type === 'tick') {
        // A long model call streaming: show its running token count (not announced, the stage start was).
        setStages((prev) => ({ ...prev, [event.stage]: { state: 'running', tokens: event.tokens } }))
      } else if (event.type === 'finished') {
        source.close()
        onFinished(event.status, event.error)
      }
    }
    source.onerror = () => setStatus('Reconnecting…')
    return () => source.close()
  }, [runId, onFinished])

  const stop = async () => {
    setStopping(true)
    try {
      await api.cancelRun(runId)
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="panel" style={{ display: 'grid', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <p role="status" aria-live="polite" style={{ margin: 0, fontWeight: 700 }}>
          {status}
          {position !== null && position > 0 ? ` (position ${position})` : ''}
        </p>
        <span className="mono" style={{ color: 'var(--muted)', marginLeft: 'auto' }}>
          model cost so far {fmtUsd(total)}
        </span>
        <button type="button" className="btn btn-danger" onClick={stop} disabled={stopping}>
          Stop
        </button>
      </div>
      <ol className="stages">
        {STAGES.map((s) => {
          const st = stages[s.key] ?? { state: 'waiting' }
          return (
            <li key={s.key} data-state={st.state}>
              <span className="mark" aria-hidden="true" />
              <strong>{s.label}</strong>
              <span className="detail">{s.model}</span>
              <span className="mono">
                {st.state === 'done'
                  ? `${st.seconds?.toFixed(1)} s${st.calls ? ` · ${st.calls} call${st.calls > 1 ? 's' : ''}` : ''}`
                  : st.state === 'running'
                    ? st.tokens
                      ? `working… ${st.tokens.toLocaleString('en-US')} tokens`
                      : 'working…'
                    : ''}
                <span className="visually-hidden">{st.state}</span>
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
