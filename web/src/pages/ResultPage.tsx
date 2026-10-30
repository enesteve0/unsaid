import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, runMedia, sampleMedia } from '../api'
import { ResultView } from '../components/ResultView'
import { RunProgress } from '../components/RunProgress'
import type { RunResult, SampleInfo } from '../types'

export function SamplePage() {
  const { id = '' } = useParams()
  const [result, setResult] = useState<RunResult | null>(null)
  const [info, setInfo] = useState<SampleInfo | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.sampleResult(id).then(setResult).catch((e: Error) => setError(e.message))
    api.samples().then((list) => setInfo(list.find((s) => s.id === id) ?? null)).catch(() => undefined)
  }, [id])

  return (
    <section style={{ paddingTop: 40 }} aria-labelledby="result-title">
      <p className="eyebrow">
        Example · {result && result.provider !== 'tokenfactory' ? "run on NVIDIA's API catalog, not Token Factory" : 'recorded run'}
      </p>
      <h1 id="result-title" style={{ fontSize: 'clamp(2rem, 4.4vw, 3.6rem)', marginBottom: 10 }}>
        {result?.title ?? 'Loading…'}
      </h1>
      {info && (
        <p className="mono" style={{ color: 'var(--muted)' }}>
          {info.credit} · <a href={info.license_url}>{info.license}</a> · <a href={info.source_url}>source</a> · descriptions
          added by Unsaid
        </p>
      )}
      {error && <p className="notice error">{error}</p>}
      {result && <ResultView result={result} media={sampleMedia(id)} />}
    </section>
  )
}

export function RunPage() {
  const { id = '' } = useParams()
  const [result, setResult] = useState<RunResult | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api
      .runResult(id)
      .then((r) => {
        setResult(r)
        setPending(false)
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) {
          api
            .runStatus(id)
            .then((s) => (['queued', 'running'].includes(s.status) ? setPending(true) : setError(s.error || `This run ${s.status}.`)))
            .catch(() => setError('This run does not exist or belongs to another browser session.'))
        } else setError(e.message)
      })
  }, [id])

  useEffect(load, [load])

  return (
    <section style={{ paddingTop: 40 }} aria-labelledby="run-title">
      <p className="eyebrow">Your run</p>
      <h1 id="run-title" style={{ fontSize: 'clamp(2rem, 4.4vw, 3.6rem)', marginBottom: 18 }}>
        {result?.title ?? 'Describing…'}
      </h1>
      {error && (
        <p className="notice error">
          {error} <Link to="/describe">Start another</Link>
        </p>
      )}
      {pending && <RunProgress runId={id} onFinished={(status, err) => (status === 'done' ? load() : setError(err ?? `Run ${status}.`))} />}
      {result && <ResultView result={result} media={runMedia(id)} runId={id} />}
    </section>
  )
}
