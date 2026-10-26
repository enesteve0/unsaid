import { fmtUsd } from '../api'
import type { RunResult } from '../types'

export function Checks({ result }: { result: RunResult }) {
  const m = result.metrics
  const minutes = result.video.duration / 60
  const items = [
    { value: `${m.talk_over_seconds.toFixed(1)} s`, label: 'spoken over the lecturer' },
    {
      value: `${m.pointing_moments_covered}/${m.pointing_moments_visual}`,
      label: 'moments where the speaker points at something, described',
    },
    { value: `${m.tiers.auto}/${m.cues}`, label: 'descriptions ready to publish without edits' },
    { value: fmtUsd(result.ledger.summary.total_usd / Math.max(minutes, 1e-6)), label: 'model cost per minute of video' },
  ]
  return (
    <div className="checks quad" role="list" aria-label="Results for this video">
      {items.map((item) => (
        <div className="check" role="listitem" key={item.label}>
          <span className="value">{item.value}</span>
          <span className="label">{item.label}</span>
        </div>
      ))}
    </div>
  )
}
