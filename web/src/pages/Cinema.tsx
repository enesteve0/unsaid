import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api, sampleMedia } from '../api'
import { Player, type Mode, type PlayerHandle } from '../components/Player'
import type { RunResult } from '../types'

/** Full-screen player for presenting in a room (and for recording the demo): /cinema/:id?mode=heard&start=&end= */
export function Cinema() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const [result, setResult] = useState<RunResult | null>(null)
  const player = useRef<PlayerHandle>(null)
  const mode = (params.get('mode') as Mode) || 'unsaid'
  const clip = useMemo(() => {
    const start = Number(params.get('start') ?? 0)
    const end = Number(params.get('end') ?? 0)
    return end > start ? { start, end } : undefined
  }, [params])

  useEffect(() => {
    api.sampleResult(id).then(setResult).catch(() => setResult(null))
  }, [id])

  return (
    <div className="cinema">
      {params.get('caption') && <p className="cinema-caption">{params.get('caption')}</p>}
      {result && <Player result={result} media={sampleMedia(id)} mode={mode} window={clip} handle={player} voiceOff={params.get('voice') === 'off'} />}
    </div>
  )
}
