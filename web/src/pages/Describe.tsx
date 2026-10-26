import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Health } from '../api'
import { BacklogPanel } from '../components/BacklogPanel'
import { RunProgress } from '../components/RunProgress'
import type { SampleInfo } from '../types'

export function Describe() {
  const navigate = useNavigate()
  const [health, setHealth] = useState<Health | null>(null)
  const [samples, setSamples] = useState<SampleInfo[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [over, setOver] = useState(false)
  const [error, setError] = useState('')
  const [runId, setRunId] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [lane, setLane] = useState<string | null>(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    api.samples().then(setSamples).catch(() => setSamples([]))
  }, [])

  const start = async (form: FormData) => {
    setError('')
    try {
      const res = await api.createRun(form)
      setRunId(res.run_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start')
    }
  }

  const submitUpload = (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError('Choose a video first, or try one of the examples.')
      return
    }
    const form = new FormData()
    form.append('file', file)
    form.append('title', title || file.name.replace(/\.[^.]+$/, ''))
    if (sourceUrl) form.append('source_url', sourceUrl)
    void start(form)
  }

  const runSample = (id: string) => {
    const form = new FormData()
    form.append('sample_id', id)
    const s = samples.find((x) => x.id === id)
    if (s?.source_url) form.append('source_url', s.source_url)
    void start(form)
  }

  const onFinished = useCallback(
    (status: 'done' | 'cancelled' | 'failed', err?: string) => {
      if (status === 'done' && runId) navigate(`/runs/${runId}`)
      else {
        setError(status === 'cancelled' ? 'Stopped. Nothing else will be spent on this run.' : err ?? 'The run failed.')
        setRunId(null)
      }
    },
    [navigate, runId],
  )

  const unlock = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await api.judge(code)
      setLane(res.lane)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid code')
    }
  }

  const paused = health?.demo_mode === 'recorded'

  return (
    <section aria-labelledby="describe-title" style={{ paddingTop: 48 }}>
      <div className="section-head">
        <div>
          <p className="eyebrow">Describe a lecture</p>
          <h1 id="describe-title" style={{ fontSize: 'clamp(2.4rem, 5vw, 4rem)' }}>
            Your clip, described in a couple of minutes.
          </h1>
          <p>
            Up to 3 minutes of lecture video. You will see every stage, which model did it and what it cost, and you can stop at
            any time. Longer lectures go to the overnight backlog on Nebius Serverless.
          </p>
        </div>
      </div>

      {paused && (
        <p className="notice">Live describing is paused right now. The examples below are real recorded runs and still work.</p>
      )}
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}

      {runId ? (
        <RunProgress runId={runId} onFinished={onFinished} />
      ) : (
        <div className="two-col">
          <form onSubmit={submitUpload} className="panel" aria-label="Upload a lecture clip">
            <div
              className="dropzone"
              data-over={over}
              onDragOver={(e) => {
                e.preventDefault()
                setOver(true)
              }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setOver(false)
                const f = e.dataTransfer.files[0]
                if (f) setFile(f)
              }}
            >
              <p style={{ fontFamily: 'var(--serif)', fontSize: '1.6rem', margin: '0 0 8px' }}>
                {file ? file.name : 'Drop a lecture clip here'}
              </p>
              <label className="btn" htmlFor="video-file" style={{ cursor: 'pointer' }}>
                Choose a video
              </label>
              <input
                id="video-file"
                className="visually-hidden"
                type="file"
                accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <p className="hint mono" style={{ marginTop: 10, color: 'var(--muted)' }}>
                MP4, MOV, WebM or MKV · up to 3 minutes · deleted after 24 hours
              </p>
            </div>
            <div className="field">
              <label htmlFor="title">Title</label>
              <input id="title" type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Week 3: Fourier series" />
            </div>
            <div className="field">
              <label htmlFor="source">Page where the video is published (optional)</label>
              <input id="source" type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://…" />
              <span className="hint">Tavily reads this page so Unsaid can use the real names of the presenter and devices instead of guessing.</span>
            </div>
            <p style={{ marginTop: 20 }}>
              <button type="submit" className="btn btn-primary" disabled={paused}>
                Describe it
              </button>
            </p>
          </form>

          <div style={{ display: 'grid', gap: 18 }}>
            <div className="panel">
              <h2 style={{ fontSize: '1.7rem' }}>Or run an example live</h2>
              <p style={{ color: 'var(--paper-dim)' }}>Openly licensed lectures, described again from scratch while you watch.</p>
              <div style={{ display: 'grid', gap: 10 }}>
                {samples.map((s) => (
                  <button key={s.id} type="button" className="btn" onClick={() => runSample(s.id)} disabled={paused}>
                    {s.title}
                    <span className="mono" style={{ marginLeft: 'auto', color: 'var(--muted)' }}>
                      {Math.round(s.duration)} s
                    </span>
                  </button>
                ))}
              </div>
            </div>
            <BacklogPanel />
            <details className="panel">
              <summary>Have an access code?</summary>
              <form onSubmit={unlock} className="field">
                <label htmlFor="code">Access code</label>
                <input id="code" type="password" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" />
                <button type="submit" className="btn" style={{ justifySelf: 'start' }}>
                  Unlock
                </button>
                {lane && <span className="hint">Unlocked: your runs use the reserved judging lane.</span>}
              </form>
            </details>
          </div>
        </div>
      )}
    </section>
  )
}
