// Small multiples: one row per metric, each on its own scale (the units differ, so they never share an axis).
// Emphasis form: Unsaid in amber, the one-shot baseline in de-emphasis gray. Values are direct-labelled in text
// colours; a legend names both series; the table below the chart is the table view.

interface Row {
  key: string
  label: string
  better: 'lower' | 'higher'
  unit?: string
  baseline: number
  unsaid: number
}

const fmt = (v: number, unit?: string) =>
  unit === '%' ? `${Math.round(v * 100)}%` : unit === '$' ? `$${v.toFixed(4)}` : unit === 's' ? `${v.toFixed(1)} s` : v.toFixed(1)

const BAR_H = 12
const GAP = 2
const LABEL_W = 92

function Bar({ value, max, y, colour, label, title }: { value: number; max: number; y: number; colour: string; label: string; title: string }) {
  const width = max > 0 ? Math.max((value / max) * 100, value > 0 ? 0.6 : 0) : 0
  return (
    <g>
      <title>{title}</title>
      <rect x="0" y={y} width={`${width}%`} height={BAR_H} rx="4" fill={colour} />
      <text x={`${Math.min(width, 100)}%`} dx="6" y={y + BAR_H - 2} className="cmp-value">
        {label}
      </text>
    </g>
  )
}

export function ComparisonBars({ rows }: { rows: Row[] }) {
  return (
    <figure className="cmp" aria-label="Unsaid compared with the one-shot baseline, one metric per row">
      <figcaption className="legend" style={{ marginBottom: 14 }}>
        <span>
          <i style={{ background: 'var(--viz-unsaid)', borderRadius: 3 }} />
          Unsaid
        </span>
        <span>
          <i style={{ background: 'var(--viz-baseline)', borderRadius: 3 }} />
          One-shot baseline
        </span>
      </figcaption>
      {rows.map((r) => {
        const max = Math.max(r.baseline, r.unsaid)
        const unsaidWins = r.better === 'lower' ? r.unsaid < r.baseline : r.unsaid > r.baseline
        const tie = r.unsaid === r.baseline
        return (
          <div className="cmp-row" key={r.key}>
            <div className="cmp-label">
              <strong>{r.label}</strong>
              <span>{r.better === 'lower' ? 'lower is better' : 'higher is better'}</span>
            </div>
            <svg className="cmp-bars" height={BAR_H * 2 + GAP} role="img" aria-label={`${r.label}: Unsaid ${fmt(r.unsaid, r.unit)}, one-shot ${fmt(r.baseline, r.unit)}${tie ? '' : unsaidWins ? '; Unsaid is better' : '; one-shot is better'}`}>
              <svg x="0" width={`calc(100% - ${LABEL_W}px)`} overflow="visible">
                <Bar value={r.unsaid} max={max} y={0} colour="var(--viz-unsaid)" label={fmt(r.unsaid, r.unit)} title={`Unsaid: ${fmt(r.unsaid, r.unit)}`} />
                <Bar value={r.baseline} max={max} y={BAR_H + GAP} colour="var(--viz-baseline)" label={fmt(r.baseline, r.unit)} title={`One-shot: ${fmt(r.baseline, r.unit)}`} />
              </svg>
            </svg>
            <span className="cmp-verdict">{tie ? 'tie' : unsaidWins ? 'Unsaid better' : 'one-shot better'}</span>
          </div>
        )
      })}
    </figure>
  )
}
