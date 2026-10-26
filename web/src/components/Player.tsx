import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState, type Ref } from 'react'
import { fmtTime } from '../api'
import { narrator } from '../lib/narrator'
import { highlightPointing, playableCues, sentenceAt, sentences } from '../lib/timeline'
import type { Cue, MediaBase, RunResult } from '../types'

export type Mode = 'heard' | 'unsaid' | 'watch'

export interface PlayerHandle {
  play: (from?: number) => void
  seek: (t: number) => void
  pause: () => void
}

interface Props {
  result: RunResult
  media: MediaBase
  mode: Mode
  onModeChange?: (mode: Mode) => void
  window?: { start: number; end: number }
  onTime?: (t: number) => void
  onCue?: (cue: Cue | null) => void
  handle?: Ref<PlayerHandle>
  compact?: boolean
}

const MODE_LABEL: Record<Mode, string> = {
  heard: 'As heard',
  unsaid: 'With Unsaid',
  watch: 'Watch',
}

export function Player({ result, media, mode, onModeChange, window: clip, onTime, onCue, handle, compact }: Props) {
  const video = useRef<HTMLVideoElement>(null)
  const spoken = useRef(new Set<string>())
  const pausedForCue = useRef(false)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(clip?.start ?? 0)
  const [active, setActive] = useState<Cue | null>(null)
  const [announce, setAnnounce] = useState('')

  const cues = useMemo(() => playableCues(result), [result])
  const lines = useMemo(() => sentences(result.transcript), [result])
  const describing = mode !== 'heard'

  const setCue = useCallback(
    (cue: Cue | null) => {
      setActive(cue)
      onCue?.(cue)
    },
    [onCue],
  )

  const resetSpoken = useCallback(
    (t: number) => {
      for (const c of cues) if (c.start >= t - 0.05) spoken.current.delete(c.id)
    },
    [cues],
  )

  const play = useCallback(
    (from?: number) => {
      const v = video.current
      if (!v) return
      narrator.prime()
      narrator.cancel()
      if (from !== undefined) {
        v.currentTime = from
        resetSpoken(from)
      }
      setCue(null)
      void v.play()
    },
    [resetSpoken, setCue],
  )

  useImperativeHandle(
    handle,
    () => ({
      play,
      seek: (t: number) => {
        const v = video.current
        if (!v) return
        narrator.cancel()
        v.currentTime = t
        resetSpoken(t)
        setCue(null)
      },
      pause: () => video.current?.pause(),
    }),
    [play, resetSpoken, setCue],
  )

  // Drive descriptions from the video clock (rAF is far tighter than timeupdate's ~4 Hz).
  useEffect(() => {
    if (!playing) return
    let raf = 0
    const tick = () => {
      const v = video.current
      if (!v) return
      const t = v.currentTime
      setTime(t)
      onTime?.(t)
      if (clip && t >= clip.end) {
        v.pause()
        return
      }
      if (describing) {
        const due = cues.find((c) => !spoken.current.has(c.id) && t >= c.start && t < c.start + 0.75)
        if (due) {
          spoken.current.add(due.id)
          setCue(due)
          setAnnounce(due.text)
          if (due.extended) {
            pausedForCue.current = true
            v.pause()
          } else {
            v.volume = 0.35
          }
          narrator.speak(due.text, () => {
            v.volume = 1
            window.setTimeout(() => setCue(null), 600)
            if (pausedForCue.current) {
              pausedForCue.current = false
              void v.play()
            }
          })
        }
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, describing, cues, clip, onTime, setCue])

  useEffect(() => () => narrator.cancel(), [])

  useEffect(() => {
    if (!describing) {
      narrator.cancel()
      setCue(null)
    }
  }, [describing, setCue])

  const onSeeked = () => {
    const v = video.current
    if (!v) return
    if (!pausedForCue.current) narrator.cancel()
    resetSpoken(v.currentTime)
    setTime(v.currentTime)
  }

  const line = sentenceAt(lines, time)
  const curtainOpen = mode === 'watch'
  const duration = result.video.duration

  return (
    <div className="player" data-compact={compact ? 'true' : undefined}>
      <div className="screen">
        <video
          ref={video}
          src={media.video}
          preload="metadata"
          playsInline
          crossOrigin="anonymous"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(pausedForCue.current)}
          onEnded={() => setPlaying(false)}
          onSeeked={onSeeked}
          onLoadedMetadata={() => {
            if (clip && video.current) video.current.currentTime = clip.start
          }}
          aria-label={`${result.title}. ${mode === 'watch' ? 'Video visible.' : 'Picture hidden: audio only.'}`}
        >
          <track kind="captions" src={media.captions} srcLang="en" label="English captions" />
          <track kind="descriptions" src={media.descriptions} srcLang="en" label="Audio descriptions by Unsaid" />
        </video>

        <div className="curtain" data-open={curtainOpen} aria-hidden={curtainOpen}>
          <div className="state">
            {playing && <span className="rec" />}
            {mode === 'heard' ? 'Picture off · lecture audio only' : 'Picture off · lecture audio + Unsaid'}
          </div>
          <div>
            {line ? (
              <p className="said">
                {highlightPointing(
                  line.text,
                  result.moments.filter((m) => m.t >= line.start - 0.5 && m.t <= line.end + 0.5),
                ).map((piece, i) => (piece.mark ? <mark key={i}>{piece.text}</mark> : <span key={i}>{piece.text}</span>))}
              </p>
            ) : (
              <p className="said">{playing ? '…' : 'Press play. Close your eyes if you like.'}</p>
            )}
            {mode === 'unsaid' && active && <p className="described">{active.text}</p>}
          </div>
        </div>

        {mode === 'watch' && active && <div className="overlay-cue">{active.text}</div>}
      </div>

      <div className="player-bar">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => (playing ? video.current?.pause() : play(clip && (time >= clip.end || time < clip.start) ? clip.start : undefined))}
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? 'Pause' : 'Play'}
        </button>
        {onModeChange && (
          <div className="mode-switch" role="group" aria-label="Listening mode">
            {(['heard', 'unsaid', 'watch'] as Mode[]).map((m) => (
              <button key={m} type="button" aria-pressed={mode === m} onClick={() => onModeChange(m)}>
                {MODE_LABEL[m]}
              </button>
            ))}
          </div>
        )}
        <span className="time mono" aria-hidden="true">
          {fmtTime(time)} / {fmtTime(duration)}
        </span>
      </div>
      <div className="visually-hidden" aria-live="polite" aria-atomic="true">
        {describing ? announce : ''}
      </div>
    </div>
  )
}
