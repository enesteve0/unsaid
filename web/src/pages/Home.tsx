import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, sampleMedia } from '../api'
import { Checks } from '../components/Checks'
import { CueCard } from '../components/CueCard'
import { Player, type Mode, type PlayerHandle } from '../components/Player'
import { STAGES } from '../lib/stages'
import { isPublished } from '../lib/timeline'
import type { Cue, RunResult, SampleInfo } from '../types'

/** The moment the home page plays: the published window if it holds a description (one in a silence first, else
 * one that pauses the video), otherwise the first pointing moment Unsaid described. */
function heroWindow(result: RunResult, sample: SampleInfo): { start: number; end: number; cue?: Cue } {
  const cues = result.cues.filter(isPublished)
  if (sample.hero) {
    const inside = cues.filter((c) => c.start >= sample.hero!.start && c.start <= sample.hero!.end)
    const cue = inside.find((c) => !c.extended) ?? inside[0]
    if (cue) return { start: sample.hero.start, end: sample.hero.end, cue }
  }
  const visual = result.moments.find((m) => result.resolutions[m.id]?.refers_to_visual && cues.some((c) => c.moment_ids.includes(m.id)))
  const cue = (visual && cues.find((c) => c.moment_ids.includes(visual.id))) ?? cues[0]
  if (!cue) return { start: 0, end: Math.min(result.video.duration, 30) }
  return { start: Math.max(cue.start - 9, 0), end: Math.min(cue.end + 3, result.video.duration), cue }
}

export function Home() {
  const [params] = useSearchParams()
  const [sample, setSample] = useState<SampleInfo | null>(null)
  const [result, setResult] = useState<RunResult | null>(null)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<Mode>('heard')
  const [heard, setHeard] = useState(false)
  const player = useRef<PlayerHandle>(null)
  const judge = params.get('judge') === '1'

  useEffect(() => {
    api
      .samples()
      .then(async (list) => {
        if (!list.length) throw new Error('No examples are published yet.')
        setSample(list[0])
        setResult(await api.sampleResult(list[0].id))
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  const hero = useMemo(() => (result && sample ? heroWindow(result, sample) : null), [result, sample])
  const heroTip = useMemo(() => {
    if (!result || !hero?.cue) return undefined
    return result.tips.find((t) => hero.cue!.moment_ids.includes(t.moment_id)) ?? result.tips.find((t) => t.t >= hero.start && t.t <= hero.end)
  }, [result, hero])

  const listen = (next: Mode) => {
    setMode(next)
    if (next === 'heard') setHeard(true)
    if (hero) player.current?.play(hero.start)
  }

  return (
    <>
      {judge && (
        <aside className="notice" aria-label="Judge tour">
          <strong>30-second tour.</strong> 1. Press <em>Hear it as a blind student does</em>. 2. Press <em>Now with Unsaid</em>.
          3. Read the checks beside it. 4. <Link to={sample ? `/samples/${sample.id}` : '/describe'}>Open the full lecture</Link> for
          the timeline, every check and the cost per model, or <Link to="/describe">describe your own clip</Link>.
        </aside>
      )}

      <section className="hero" aria-labelledby="hero-title" style={{ paddingTop: 48 }}>
        <div>
          <p className="eyebrow reveal">Audio description for lecture video</p>
          <h1 id="hero-title" className="reveal reveal-2">
            <span className="quote">“As you can</span> <span className="strike">see</span>…”
          </h1>
          <p className="lede reveal reveal-3">
            A blind student can’t. Lecturers point at curves, equations and diagrams without saying what they show.{' '}
            <strong>Unsaid finds those moments and describes them in the pauses, without ever talking over the lecture.</strong>
          </p>
          <div className="ab reveal reveal-4">
            <button type="button" className="btn" onClick={() => listen('heard')} disabled={!hero}>
              <span>
                ① Hear it as a blind student does
                <small>Picture off, lecture audio only</small>
              </span>
            </button>
            <button type="button" className={`btn ${heard ? 'btn-primary' : ''}`} onClick={() => listen('unsaid')} disabled={!hero}>
              <span>
                ② Now with Unsaid
                <small>Same clip, with the unsaid described</small>
              </span>
            </button>
          </div>
        </div>

        <div className="reveal reveal-3">
          {error && <p className="notice error">{error}</p>}
          {result && sample && hero ? (
            <>
              <Player result={result} media={sampleMedia(sample.id)} mode={mode} onModeChange={setMode} window={hero} handle={player} compact />
              <p className="mono" style={{ color: 'var(--muted)', marginTop: 10 }}>
                {sample.title} — {sample.credit}.{' '}
                <a href={sample.license_url}>{sample.license}</a>. Descriptions added by Unsaid
                {result.provider === 'tokenfactory' ? ' on Nebius Token Factory.' : ", in a run of the same models on NVIDIA's API catalog, not Token Factory."}
              </p>
            </>
          ) : (
            !error && <div className="player" style={{ aspectRatio: '16 / 9' }} aria-busy="true" />
          )}
        </div>
      </section>

      {result && hero?.cue && (
        <section aria-labelledby="pause-title">
          <div className="section-head">
            <div>
              <p className="eyebrow">What Unsaid said in that pause</p>
              <h2 id="pause-title">Checked by code, then by a second look at the frames.</h2>
            </div>
            {sample && (
              <Link className="btn" to={`/samples/${sample.id}`}>
                Open the whole lecture →
              </Link>
            )}
          </div>
          <div className="two-col">
            <CueCard cue={hero.cue} result={result} onPlay={(t) => player.current?.play(t)} />
            <Checks result={result} />
          </div>
          {heroTip && (
            <div className="panel" style={{ marginTop: 18, display: 'grid', gap: 10 }}>
              <p className="eyebrow">And the fix at the source: a tip for the lecturer</p>
              <p style={{ margin: 0, color: 'var(--paper-dim)' }}>Said: “{heroTip.said}”</p>
              <p style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: '1.45rem', lineHeight: 1.3 }}>
                Next time, try: “{heroTip.suggestion}”
              </p>
            </div>
          )}
        </section>
      )}

      <section aria-labelledby="how-title">
        <div className="section-head">
          <div>
            <p className="eyebrow">How it works</p>
            <h2 id="how-title">Four Nemotron models, each doing the one job it is best at.</h2>
            <p>
              Only Super VL can see, so it watches and later checks. Only Ultra can hold a whole lecture in mind, so it plans.
              Lightning rewrites quickly and cheaply until a description fits its silence. Nano classifies. Code has the last word.
            </p>
          </div>
        </div>
        <ol className="steps" style={{ listStyle: 'none', padding: 0 }}>
          {STAGES.map((s, i) => (
            <li className="step" key={s.key}>
              <span className="n">{String(i + 1).padStart(2, '0')}</span>
              <h3>{s.label}</h3>
              <span className="model">{s.model}</span>
              <p>{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="why-title">
        <div className="section-head">
          <div>
            <p className="eyebrow">Why</p>
            <h2 id="why-title">Most of what a lecture shows is never fully said.</h2>
          </div>
        </div>
        <div className="checks">
          <div className="check">
            <span className="value">72%</span>
            <span className="label">
              of 610 visual elements in 90 presentation videos were insufficiently described by the speaker (Peng et al., CHI 2021)
            </span>
          </div>
          <div className="check">
            <span className="value">2.2 bn</span>
            <span className="label">people, at least, live with a near or distance vision impairment (WHO fact sheet)</span>
          </div>
          <div className="check">
            <span className="value">Apr 2027</span>
            <span className="label">
              US public universities must meet WCAG 2.1 AA, which requires audio description (ADA Title II rule)
            </span>
          </div>
          <div className="check">
            <span className="value">$0.90–9/min</span>
            <span className="label">list prices for AI audio description today; human description costs more and takes days</span>
          </div>
        </div>
        <p style={{ marginTop: 28 }}>
          <Link className="btn btn-primary" to="/describe">
            Describe a lecture clip →
          </Link>
        </p>
      </section>
    </>
  )
}
