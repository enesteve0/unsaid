import type { Cue, RunResult } from '../types'

interface Props {
  result: RunResult
  current: number
  activeCueId?: string | null
  onSeek: (t: number) => void
}

const W = 1000
const H = 104

export function Timeline({ result, current, activeCueId, onSeek }: Props) {
  const duration = result.video.duration || 1
  const x = (t: number) => (Math.max(0, Math.min(t, duration)) / duration) * W
  const step = duration > 600 ? 60 : duration > 180 ? 30 : duration > 60 ? 10 : 5
  const ticks = Array.from({ length: Math.floor(duration / step) + 1 }, (_, i) => i * step)
  const visualMoments = result.moments.filter((m) => result.resolutions[m.id]?.refers_to_visual)
  const inline = result.cues.filter((c) => !c.extended && c.tier !== 'never')
  const extended = result.cues.filter((c) => c.extended && c.tier !== 'never')

  const summary =
    `Timeline of ${Math.round(duration)} seconds: ${result.speech.length} stretches of speech, ` +
    `${result.gaps.length} silences, ${inline.length} descriptions placed inside silences, ` +
    `${extended.length} extended descriptions, ${visualMoments.length} pointing moments.`

  const cueClass = (c: Cue) =>
    ['cue', c.tier === 'review' ? 'review' : '', c.extended ? 'extended' : '', c.id === activeCueId ? 'active' : '']
      .filter(Boolean)
      .join(' ')

  return (
    <figure style={{ margin: 0 }}>
      <svg
        className="timeline"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={summary}
        preserveAspectRatio="none"
        onClick={(e) => {
          const box = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
          onSeek(((e.clientX - box.left) / box.width) * duration)
        }}
      >
        {result.gaps.map((g) => (
          <rect key={g.id} className="gap" x={x(g.start)} y={34} width={Math.max(x(g.end) - x(g.start), 1)} height={26} />
        ))}
        {result.speech.map((s, i) => (
          <rect key={i} className="speech" x={x(s.start)} y={38} width={Math.max(x(s.end) - x(s.start), 1)} height={18} rx={1} />
        ))}
        {inline.map((c) => (
          <rect key={c.id} className={cueClass(c)} x={x(c.start)} y={34} width={Math.max(x(c.end) - x(c.start), 3)} height={26} rx={1} />
        ))}
        {extended.map((c) => (
          <path key={c.id} className={cueClass(c)} d={`M${x(c.start)} 36 l8 11 l-8 11 l-8 -11 z`} />
        ))}
        {visualMoments.map((m) => (
          <path key={m.id} className="moment" d={`M${x(m.t) - 5} 14 h10 l-5 9 z`} />
        ))}
        {result.segments.slice(1).map((s) => (
          <line key={s.id} className="slide" x1={x(s.start)} x2={x(s.start)} y1={66} y2={74} />
        ))}
        {ticks.map((t) => (
          <text key={t} className="axis" x={x(t) + 2} y={92}>
            {Math.floor(t / 60)}:{String(Math.round(t % 60)).padStart(2, '0')}
          </text>
        ))}
        <line className="playhead" x1={x(current)} x2={x(current)} y1={4} y2={78} />
      </svg>
      <figcaption className="legend">
        <span>
          <i style={{ background: 'var(--speech)' }} />
          speech
        </span>
        <span>
          <i style={{ border: '1px dashed var(--line)' }} />
          silence
        </span>
        <span>
          <i style={{ background: 'var(--amber)' }} />
          description in a silence
        </span>
        <span>
          <i style={{ border: '1.5px solid var(--amber)', transform: 'rotate(45deg)', width: 9, height: 9 }} />
          extended (video pauses)
        </span>
        <span>
          <i style={{ background: 'var(--vermilion)', clipPath: 'polygon(0 0, 100% 0, 50% 100%)', height: 9, width: 12 }} />
          speaker points at something
        </span>
      </figcaption>
    </figure>
  )
}
