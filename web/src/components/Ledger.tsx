import { fmtUsd } from '../api'
import type { LedgerSummary } from '../types'

const ROLE: Record<string, string> = {
  'Nemotron 3.5 Super VL': 'Watches every segment, then checks every description against the frames',
  'Nemotron 3 Ultra': 'Reads the whole lecture at once and decides what is unsaid and where it fits',
  'Nemotron 3.5 Lightning': 'Writes and rewrites each description until it fits its silence',
  'Nemotron 3 Nano': 'Decides what each “this” or “here” points at',
  'Nemotron 3 Super': 'Fallback for planning when Ultra is unavailable',
}

export function Ledger({ summary, minutes }: { summary: LedgerSummary; minutes: number }) {
  const rows = Object.entries(summary.by_model).sort((a, b) => b[1].cost_usd - a[1].cost_usd)
  const max = Math.max(summary.ultra_only_usd, summary.total_usd, 1e-9)
  return (
    <div className="panel">
      <table>
        <caption className="visually-hidden">Model calls and cost for this video</caption>
        <thead>
          <tr>
            <th scope="col">Model on Nebius Token Factory</th>
            <th scope="col" className="num">
              Calls
            </th>
            <th scope="col" className="num">
              Tokens in (cached)
            </th>
            <th scope="col" className="num">
              Tokens out
            </th>
            <th scope="col" className="num">
              Cost
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, row]) => (
            <tr key={label}>
              <td>
                <strong>{label}</strong>
                <div style={{ color: 'var(--paper-dim)', fontSize: '0.84rem' }}>{ROLE[label] ?? ''}</div>
              </td>
              <td className="num">{row.calls}</td>
              <td className="num">
                {row.prompt_tokens.toLocaleString()} ({row.cached_tokens.toLocaleString()})
              </td>
              <td className="num">{row.completion_tokens.toLocaleString()}</td>
              <td className="num">{fmtUsd(row.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'grid', gap: 14, marginTop: 20 }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Routed across four Nemotron models</span>
            <span className="mono">{fmtUsd(summary.total_usd)}</span>
          </div>
          <div className="bar" aria-hidden="true">
            <span style={{ width: `${(summary.total_usd / max) * 100}%` }} />
          </div>
        </div>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Same text work done by Ultra alone (vision stays on Super VL)</span>
            <span className="mono">{fmtUsd(summary.ultra_only_usd)}</span>
          </div>
          <div className="bar cf" aria-hidden="true">
            <span style={{ width: `${(summary.ultra_only_usd / max) * 100}%` }} />
          </div>
        </div>
        <p className="mono" style={{ color: 'var(--paper-dim)', margin: 0 }}>
          {minutes > 0 && <>{fmtUsd(summary.total_usd / minutes)} per minute of video · </>}
          {summary.usd_per_accepted_cue !== undefined && <>{fmtUsd(summary.usd_per_accepted_cue)} per description ready to publish · </>}
          {summary.calls} calls{summary.failed_calls ? `, ${summary.failed_calls} retried or rerouted` : ''}
        </p>
      </div>
    </div>
  )
}
