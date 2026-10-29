import { useRef, useState } from 'react'
import type { Cue, MediaBase, RunResult } from '../types'
import { CueCard } from './CueCard'
import { Ledger } from './Ledger'
import { Player, type Mode, type PlayerHandle } from './Player'
import { Script } from './Script'
import { Timeline } from './Timeline'
import { Checks } from './Checks'

type Tab = 'script' | 'review' | 'tips' | 'ledger' | 'exports' | 'reasoning'

const TABS: { key: Tab; label: string }[] = [
  { key: 'script', label: 'Script' },
  { key: 'review', label: 'Descriptions & checks' },
  { key: 'tips', label: 'Lecturer tips' },
  { key: 'ledger', label: 'Models & cost' },
  { key: 'exports', label: 'Exports' },
  { key: 'reasoning', label: 'What Ultra decided' },
]

const EXPORTS = [
  { file: 'descriptions.vtt', label: 'Audio description track (WebVTT, kind="descriptions")' },
  { file: 'captions.vtt', label: 'Captions (WebVTT)' },
  { file: 'captions.srt', label: 'Captions (SRT)' },
  { file: 'transcript.html', label: 'Transcript with descriptions inline (text alternative, WCAG 1.2.3)' },
  { file: 'markers.fcpxml', label: 'Final Cut Pro markers (one per description)' },
  { file: 'result.json', label: 'Everything, as JSON' },
]

export function ResultView({ result: initial, media, runId }: { result: RunResult; media: MediaBase; runId?: string }) {
  const [result, setResult] = useState(initial)
  const [mode, setMode] = useState<Mode>('watch')
  const [time, setTime] = useState(0)
  const [cue, setCue] = useState<Cue | null>(null)
  const [tab, setTab] = useState<Tab>('script')
  const player = useRef<PlayerHandle>(null)
  const seek = (t: number) => player.current?.play(t)
  const minutes = result.video.duration / 60

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 28 }}>
      <div className="two-col">
        <Player result={result} media={media} mode={mode} onModeChange={setMode} onTime={setTime} onCue={setCue} handle={player} />
        <div style={{ display: 'grid', gap: 18 }}>
          <Checks result={result} />
          {result.bible.summary && (
            <p style={{ color: 'var(--paper-dim)', margin: 0 }}>
              <span className="eyebrow">Ultra's one-line summary</span>
              <br />
              {result.bible.summary}
            </p>
          )}
          {(result.metrics.flagged_by_check ?? 0) > 0 && (
            <p style={{ margin: 0, color: 'var(--paper-dim)' }}>
              The frame check flagged {result.metrics.flagged_by_check} draft
              {result.metrics.flagged_by_check === 1 ? '' : 's'} with claims the picture did not support; Lightning corrected{' '}
              {result.metrics.corrected_after_check ?? 0} and the rest wait for a person.
            </p>
          )}
          {result.failures && result.failures.length > 0 && (
            <p className="notice">
              {result.failures.length} segment{result.failures.length > 1 ? 's' : ''} could not be read and{' '}
              {result.failures.length > 1 ? 'were' : 'was'} skipped; nothing was made up for {result.failures.length > 1 ? 'them' : 'it'}.
            </p>
          )}
        </div>
      </div>

      <Timeline result={result} current={time} activeCueId={cue?.id} onSeek={seek} />

      <div>
        <div className="mode-switch" role="tablist" aria-label="Details">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              id={`tab-${t.key}`}
              aria-selected={tab === t.key}
              aria-controls={`panel-${t.key}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} style={{ marginTop: 18 }}>
          {tab === 'script' && <Script result={result} current={time} activeCueId={cue?.id} onSeek={seek} follow />}
          {tab === 'review' && (
            <div className="cues">
              {result.cues.map((c) => (
                <CueCard
                  key={c.id}
                  cue={c}
                  result={result}
                  runId={runId}
                  active={cue?.id === c.id}
                  onPlay={seek}
                  onSaved={(updated) => setResult({ ...result, cues: result.cues.map((x) => (x.id === updated.id ? updated : x)) })}
                />
              ))}
              {result.cues.length === 0 && <p>No descriptions were needed: everything visual was also said.</p>}
            </div>
          )}
          {tab === 'tips' && (
            <div className="cues">
              <p style={{ color: 'var(--paper-dim)', maxWidth: '70ch' }}>
                The best description is the one the lecturer says aloud. For each moment where the speech points at something
                instead of saying it, here is a sentence that carries the picture in words (W3C calls this integrated
                description).
              </p>
              {result.tips.map((tip) => (
                <article className="cue-card" key={tip.moment_id}>
                  <header>
                    <span className="mono">{Math.floor(tip.t / 60)}:{String(Math.floor(tip.t % 60)).padStart(2, '0')}</span>
                    <button type="button" className="btn btn-ghost" style={{ marginLeft: 'auto', padding: '8px 12px' }} onClick={() => seek(Math.max(tip.t - 3, 0))}>
                      Hear the original
                    </button>
                  </header>
                  <p style={{ margin: 0, color: 'var(--paper-dim)' }}>
                    <span className="eyebrow">Said</span>
                    <br />“{tip.said}”
                  </p>
                  <p className="text" style={{ margin: 0 }}>
                    <span className="eyebrow">Next time, try</span>
                    <br />“{tip.suggestion}”
                  </p>
                </article>
              ))}
              {result.tips.length === 0 && <p>No unsaid pointing moments in this video.</p>}
            </div>
          )}
          {tab === 'ledger' && <Ledger summary={result.ledger.summary} minutes={minutes} />}
          {tab === 'exports' && (
            <ul className="panel" style={{ listStyle: 'none', margin: 0, display: 'grid', gap: 10 }}>
              {EXPORTS.map((e) => (
                <li key={e.file}>
                  <a href={media.files(e.file)} download={e.file !== 'transcript.html' ? e.file : undefined}>
                    {e.label}
                  </a>{' '}
                  <span className="mono" style={{ color: 'var(--muted)' }}>
                    {e.file}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {tab === 'reasoning' && (
            <div className="panel" style={{ display: 'grid', gap: 18 }}>
              <p style={{ margin: 0, color: 'var(--paper-dim)' }}>
                Nemotron 3 Ultra read the full transcript, every segment report and every silence in one context, then wrote this
                plan. Facts marked “already said” are never described.
              </p>
              <table>
                <thead>
                  <tr>
                    <th scope="col">Time</th>
                    <th scope="col">Visual fact</th>
                    <th scope="col">Importance</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {result.bible.visual_facts.map((f) => (
                    <tr key={f.id}>
                      <td className="mono">{f.t.toFixed(1)} s</td>
                      <td>{f.fact}</td>
                      <td className="num">{'●'.repeat(f.importance)}</td>
                      <td>{f.already_spoken ? 'already said' : result.cues.some((c) => c.fact_ids.includes(f.id)) ? 'described' : 'left out (no room)'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.context.sources.length > 0 && (
                <div>
                  <h3 style={{ fontSize: '1.3rem' }}>Context via Tavily</h3>
                  <ul>
                    {result.context.sources.map((s) => (
                      <li key={s.request_id + s.url}>
                        <a href={s.url}>{s.title || s.url}</a> — {s.used_for}{' '}
                        <span className="mono" style={{ color: 'var(--muted)' }}>
                          {s.request_id}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
