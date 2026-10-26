import { useEffect, useState } from 'react'
import { api, fmtUsd, type Backlog } from '../api'

/** The last overnight run of the Nebius Serverless Job that describes a lecture backlog. */
export function BacklogPanel() {
  const [backlog, setBacklog] = useState<Backlog | null>(null)

  useEffect(() => {
    api.backlog().then(setBacklog).catch(() => setBacklog({ available: false }))
  }, [])

  return (
    <section className="panel" aria-labelledby="backlog-title">
      <p className="eyebrow">Nebius Serverless Job</p>
      <h2 id="backlog-title" style={{ fontSize: '1.7rem', marginTop: 6 }}>
        Overnight backlog
      </h2>
      <p style={{ color: 'var(--paper-dim)' }}>
        Longer lectures are described by a batch job on Nebius Serverless: it resumes where it stopped, never spends past
        its dollar cap, and leaves a digest for the morning.
      </p>
      {!backlog?.available ? (
        <p className="mono" style={{ color: 'var(--muted)' }}>
          No overnight run recorded yet.
        </p>
      ) : (
        <>
          <p className="mono" style={{ color: 'var(--muted)' }}>
            Last run {backlog.finished_at} · {backlog.ready} ready · {backlog.need_review} with descriptions to review ·{' '}
            {fmtUsd(backlog.spent_usd ?? 0)} of a {fmtUsd(backlog.budget_usd ?? 0)} cap
          </p>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 8 }}>
            {backlog.lectures?.map((l) => (
              <li key={l.id} style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
                <span className={`badge ${l.status === 'ready' ? 'auto' : l.status === 'failed' ? 'never' : 'review'}`}>{l.status}</span>
                <span>{l.title}</span>
                {l.cues !== undefined && (
                  <span className="mono" style={{ color: 'var(--muted)' }}>
                    {l.auto}/{l.cues} ready{l.review ? `, ${l.review} to review` : ''}
                  </span>
                )}
                {l.reason && (
                  <span className="mono" style={{ color: 'var(--muted)' }}>
                    {l.reason}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
