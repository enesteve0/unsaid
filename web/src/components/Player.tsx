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
  /** Show descriptions without speaking them (used when recording the demo; the voice is added afterwards). */
  voiceOff?: boolean
}

const MODE_LABEL: Record<Mode, string> = {
  heard: 'As heard',
  unsaid: 'With Unsaid',
  watch: 'Watch',
}

export function Player({ result, media, mode, onModeChange, window: clip, onTime, onCue, handle, compact, voiceOff }: Props) {
  const video = useRef<HTMLVideoElement>(null)
  const spoken = useRef(new Set<string>())
  const pausedForCue = useRef(false)
  const [playing, setPlaying] = useState(false)
  const [time, setTime] = useState(clip?.start ?? 0)
  const [active, setActive] = useState<Cue | null>(null)
  const [announce, setAnnounce] = useState('')
  // Screen-reader users get descriptions through their own reader instead of a second voice.
  const [output, setOutput] = useState<'speech' | 'reader'>('speech')

  const cues = useMemo(() => playableCues(result), [result])
  const lines = useMemo(() => sentences(result.transcript), [result])
  const describing = mode !== 'heard'

  const setCue = useCallback(
    (next: Cue | null | ((current: Cue | null) => Cue | null)) => {
      setActive((current) => {
        const value = typeof next === 'function' ? next(current) : next
        if (value !== current) onCue?.(value)
        return value
      })
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
          // Keep the text on screen for at least as long as it takes to say, even if speech ends early.
          const shownUntil = performance.now() + Math.max(due.end - due.start, 1.5) * 1000
          const silent = voiceOff || output === 'reader'
          const speak = silent ? (_: string, done: () => void) => window.setTimeout(done, (due.end - due.start) * 1000) : narrator.speak.bind(narrator)
          speak(due.text, () => {
            v.volume = 1
            const linger = Math.max(shownUntil - performance.now(), 0) + 600
            window.setTimeout(() => setCue((current) => (current?.id === due.id ? null : current)), linger)
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
  }, [playing, describing, cues, clip, onTime, setCue, voiceOff, output])

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
          poster={media.poster}
          preload="auto"
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
        {describing && (
          <button
            type="button"
            className="btn btn-ghost"
            style={{ padding: '10px 12px' }}
            aria-pressed={output === 'reader'}
            onClick={() => {
              narrator.cancel()
              setOutput(output === 'speech' ? 'reader' : 'speech')
            }}
            title="Send descriptions to your screen reader instead of speaking them"
          >
            {output === 'reader' ? 'Descriptions: screen reader' : 'Descriptions: spoken'}
          </button>
        )}
        <span className="time mono" aria-hidden="true">
          {fmtTime(time)} / {fmtTime(duration)}
        </span>
      </div>
      <div className="visually-hidden" aria-live={output === 'reader' ? 'assertive' : 'off'} aria-atomic="true">
        {describing && output === 'reader' ? announce : ''}
      </div>
    </div>
  )
}
