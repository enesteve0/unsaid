import { useState } from 'react'
import { api, fmtTime } from '../api'
import type { Cue, RunResult } from '../types'

interface Props {
  cue: Cue
  result: RunResult
  active?: boolean
  runId?: string
  onPlay: (t: number) => void
  onSaved?: (cue: Cue) => void
}

const TIER_LABEL = { auto: 'Ready', review: 'Needs review', never: 'Withheld' } as const

function gateRows(cue: Cue, result: RunResult) {
  const has = (prefix: string) => cue.gate_failures.some((f) => f.startsWith(prefix))
  const gap = result.gaps.find((g) => g.id === cue.gap_id)
  const rows: { state: 'pass' | 'fail' | 'warn'; text: string }[] = []
  if (cue.extended) {
    rows.push({ state: 'warn', text: 'No silence long enough: the player pauses the video for it (WCAG 1.2.7 extended description)' })
  } else if (gap) {
    rows.push({
      state: has('too_long') ? 'fail' : 'pass',
      text: `Fits the ${(gap.end - gap.start).toFixed(1)} s silence (needs ${(cue.end - cue.start).toFixed(1)} s)`,
    })
    rows.push({ state: has('talks_over_speech') ? 'fail' : 'pass', text: 'Never talks over the lecturer' })
  }
  rows.push({ state: has('number_not_on_screen') ? 'fail' : 'pass', text: 'Every number is printed on screen' })
  rows.push({ state: has('unknown_name') ? 'fail' : 'pass', text: 'Names only from the screen, the speech or the source page' })
  rows.push({ state: has('banned_phrase') ? 'fail' : 'pass', text: 'Describer style: no “we see”, present tense' })
  for (const w of cue.gate_warnings) rows.push({ state: 'warn', text: w === 'speculation' ? 'Hedged wording (appears, seems)' : 'Past tense' })
  return rows
}

export function CueCard({ cue, result, active, runId, onPlay, onSaved }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(cue.text)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const claims = cue.verification?.claims ?? []

  const save = async () => {
    if (!runId) return
    setBusy(true)
    setMessage(null)
    try {
      const res = await api.editCue(runId, cue.id, draft)
      if (res.passed) {
        onSaved?.({ ...cue, text: draft, gate_failures: [], gate_warnings: res.warnings, tier: res.warnings.length ? 'review' : 'auto', edited: true })
        setEditing(false)
      } else {
        setMessage(`Not saved: ${res.failures.join('; ')}`)
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="cue-card" data-active={active ? 'true' : 'false'} aria-label={`Description at ${fmtTime(cue.start)}`}>
      <header>
        <span className="mono">{fmtTime(cue.start)}</span>
        <span className={`badge ${cue.tier}`}>{TIER_LABEL[cue.tier]}</span>
        {cue.extended && <span className="badge ext">Extended</span>}
        {cue.repairs > 0 && <span className="badge review">Rewritten {cue.repairs}× to fit</span>}
        {cue.edited && <span className="badge auto">Edited by a person</span>}
        {cue.corrected_from && <span className="badge auto">Corrected after the frame check</span>}
        {cue.sources.length > 0 && <span className="badge tavily">Context via Tavily</span>}
        <button type="button" className="btn btn-ghost" style={{ marginLeft: 'auto', padding: '8px 12px' }} onClick={() => onPlay(Math.max(cue.start - 4, 0))}>
          Play this moment
        </button>
      </header>

      {editing ? (
        <div>
          <label className="visually-hidden" htmlFor={`edit-${cue.id}`}>
            Edit description
          </label>
          <textarea id={`edit-${cue.id}`} value={draft} onChange={(e) => setDraft(e.target.value)} />
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button type="button" className="btn btn-primary" onClick={save} disabled={busy}>
              Check and save
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <p className="text" style={{ margin: 0 }}>
          {cue.text}
        </p>
      )}
      {message && <p className="notice error">{message}</p>}
      {cue.corrected_from && (
        <p style={{ margin: 0, color: 'var(--muted)', fontSize: '0.88rem' }}>
          First draft, rejected by the frame check: <s>{cue.corrected_from}</s>
        </p>
      )}

      <ul className="gate-list" aria-label="Checks">
        {gateRows(cue, result).map((row, i) => (
          <li key={i} className={row.state}>
            {row.text}
          </li>
        ))}
      </ul>

      {claims.length > 0 && (
        <details>
          <summary className="mono">Checked against the frames by Nemotron 3.5 Super VL: {claims.filter((c) => c.verdict === 'supported').length} of {claims.length} claims visible</summary>
          <ul className="gate-list" style={{ marginTop: 8, display: 'grid' }}>
            {claims.map((c, i) => (
              <li key={i} className={c.verdict === 'supported' ? 'pass' : c.verdict === 'contradicted' ? 'fail' : 'warn'}>
                {c.claim} — {c.verdict.replace('_', ' ')}
              </li>
            ))}
          </ul>
        </details>
      )}

      {runId && !editing && (
        <div>
          <button type="button" className="btn btn-ghost" style={{ padding: '8px 12px' }} onClick={() => setEditing(true)}>
            Edit
          </button>
        </div>
      )}
    </article>
  )
}
