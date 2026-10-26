import { useEffect, useState } from 'react'
import { api } from '../api'
import { ComparisonBars } from '../components/ComparisonBars'

interface SystemRow {
  key: string
  label: string
  metrics: Record<string, number>
}

type MetricLabels = Record<string, { label: string; better: 'lower' | 'higher'; unit?: string }>

interface Split {
  key: string
  label: string
  clips: number
  minutes: number
  systems: SystemRow[]
}

interface Report {
  available?: boolean
  generated_at?: string
  clips?: number
  minutes?: number
  runs?: number
  systems?: SystemRow[]
  splits?: Split[]
  metric_labels?: MetricLabels
  failures?: { clip: string; t: number; text: string; problem: string }[]
  notes?: string[]
}

const fmt = (v: number, unit?: string) =>
  unit === '%' ? `${(v * 100).toFixed(0)}%` : unit === '$' ? `$${v.toFixed(4)}` : unit === 's' ? `${v.toFixed(2)} s` : v.toFixed(2)

function MetricsTable({ systems, labels, caption }: { systems: SystemRow[]; labels: MetricLabels; caption: string }) {
  return (
    <div className="panel" style={{ overflowX: 'auto' }}>
      <table>
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">System</th>
            {Object.entries(labels).map(([key, meta]) => (
              <th key={key} scope="col" className="num">
                {meta.label}
                <br />
                <span style={{ textTransform: 'none', letterSpacing: 0 }}>{meta.better === 'lower' ? 'lower is better' : 'higher is better'}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {systems.map((s) => (
            <tr key={s.key}>
              <th scope="row" style={{ textTransform: 'none', letterSpacing: 0, font: '700 0.95rem var(--sans)', color: s.key === 'unsaid' ? 'var(--amber)' : 'var(--paper)' }}>
                {s.label}
              </th>
              {Object.entries(labels).map(([key, meta]) => (
                <td key={key} className="num">
                  {s.metrics[key] === undefined ? '—' : fmt(s.metrics[key], meta.unit)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Evaluation() {
  const [report, setReport] = useState<Report | null>(null)

  useEffect(() => {
    api
      .evaluation()
      .then((r) => setReport(r as Report))
      .catch(() => setReport({ available: false }))
  }, [])

  const systems = report?.systems ?? []
  const labels = report?.metric_labels ?? {}

  return (
    <section style={{ paddingTop: 48 }} aria-labelledby="eval-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Evaluation</p>
          <h1 id="eval-title" style={{ fontSize: 'clamp(2.2rem, 5vw, 4rem)' }}>
            Does it beat describing the whole video in one shot?
          </h1>
          <p>
            The obvious way to build AI audio description is one call to a vision model: “describe this video with timestamps”.
            We compare that baseline with Unsaid’s routed pipeline on the same openly licensed clips, and publish where Unsaid fails.
          </p>
        </div>
      </div>

      {!report?.available ? (
        <p className="notice">The evaluation report is generated from the deployed build; it is not available yet.</p>
      ) : (
        <>
          <p className="mono" style={{ color: 'var(--muted)' }}>
            {report.clips} {report.clips === 1 ? 'clip' : 'clips'} · {report.minutes?.toFixed(1)} minutes of video
            {(report.runs ?? 1) > 1 ? ` · each described ${report.runs} times` : ''} · generated {report.generated_at}
          </p>
          {systems.length === 2 && (
            <div className="panel" style={{ marginBottom: 22 }}>
              <ComparisonBars
                rows={Object.entries(labels).map(([key, meta]) => ({
                  key,
                  label: meta.label,
                  better: meta.better,
                  unit: meta.unit,
                  baseline: systems.find((s) => s.key === 'oneshot')?.metrics[key] ?? 0,
                  unsaid: systems.find((s) => s.key === 'unsaid')?.metrics[key] ?? 0,
                }))}
              />
            </div>
          )}
          <MetricsTable systems={systems} labels={labels} caption="Metrics per system, all clips" />

          {report.splits &&
            report.splits.length > 1 &&
            report.splits.map((split) => (
              <section key={split.key} aria-labelledby={`split-${split.key}`} style={{ marginTop: 32 }}>
                <h2 id={`split-${split.key}`} style={{ fontSize: '1.6rem', marginBottom: 6 }}>
                  {split.label}
                </h2>
                <p className="mono" style={{ color: 'var(--muted)', marginTop: 0 }}>
                  {split.clips} {split.clips === 1 ? 'clip' : 'clips'} · {split.minutes.toFixed(1)} minutes of video
                </p>
                <MetricsTable systems={split.systems} labels={labels} caption={`Metrics per system, ${split.label}`} />
              </section>
            ))}

          {report.notes && (
            <ul style={{ color: 'var(--paper-dim)', marginTop: 20 }}>
              {report.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}

          <h2 style={{ marginTop: 48, fontSize: '2.2rem' }}>Where Unsaid fails</h2>
          <div className="cues" style={{ marginTop: 18 }}>
            {(report.failures ?? []).map((f, i) => (
              <article className="cue-card" key={i}>
                <header>
                  <span className="mono">
                    {f.clip} · {f.t.toFixed(1)} s
                  </span>
                  <span className="badge never">{f.problem}</span>
                </header>
                <p className="text" style={{ margin: 0 }}>
                  {f.text}
                </p>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
