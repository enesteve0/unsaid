import { useEffect, useMemo, useRef } from 'react'
import { fmtTime } from '../api'
import { highlightPointing, playableCues, sentences } from '../lib/timeline'
import type { RunResult } from '../types'

interface Props {
  result: RunResult
  current: number
  activeCueId?: string | null
  onSeek: (t: number) => void
  follow?: boolean
}

type Line = { kind: 'speech' | 'cue'; t: number; end: number; text: string; id: string; extended?: boolean }

/** The lecture as a screenplay: what is said, and (in amber) what Unsaid adds in the pauses. */
export function Script({ result, current, activeCueId, onSeek, follow }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const lines = useMemo<Line[]>(() => {
    const speech = sentences(result.transcript).map((s, i) => ({ kind: 'speech' as const, t: s.start, end: s.end, text: s.text, id: `s${i}` }))
    const cues = playableCues(result).map((c) => ({ kind: 'cue' as const, t: c.start, end: c.end, text: c.text, id: c.id, extended: c.extended }))
    return [...speech, ...cues].sort((a, b) => a.t - b.t || (a.kind === 'cue' ? 1 : -1))
  }, [result])

  const activeId =
    activeCueId ?? lines.find((l) => l.kind === 'speech' && current >= l.t - 0.1 && current <= l.end + 0.3)?.id

  useEffect(() => {
    if (!follow || !box.current || !activeId) return
    const el = box.current.querySelector<HTMLElement>(`[data-line="${activeId}"]`)
    if (el) box.current.scrollTop = el.offsetTop - box.current.clientHeight / 3
  }, [activeId, follow])

  return (
    <div className="script" ref={box} role="list" aria-label="Transcript with descriptions">
      {lines.map((line) => (
        <button
          type="button"
          role="listitem"
          key={line.id}
          data-line={line.id}
          className={`script-line ${line.kind} ${line.id === activeId ? 'active' : ''}`}
          onClick={() => onSeek(line.t)}
          aria-label={`${line.kind === 'cue' ? 'Description' : 'Speech'} at ${fmtTime(line.t)}: ${line.text}. Play from here.`}
        >
          <span className="t">{fmtTime(line.t)}</span>
          <span className="text">
            {line.kind === 'speech'
              ? highlightPointing(
                  line.text,
                  result.moments.filter((m) => m.t >= line.t - 0.5 && m.t <= line.end + 0.5 && result.resolutions[m.id]?.refers_to_visual),
                ).map((p, i) => (p.mark ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>))
              : `${line.extended ? '[pauses the video] ' : ''}${line.text}`}
          </span>
        </button>
      ))}
    </div>
  )
}
