import type { Cue, Moment, RunResult, Word } from '../types'

export interface Sentence {
  start: number
  end: number
  text: string
  words: Word[]
}

/** Group ASR words into sentences (terminal punctuation or a 12-second cap). */
export function sentences(words: Word[]): Sentence[] {
  const out: Sentence[] = []
  let cur: Word[] = []
  const flush = () => {
    if (!cur.length) return
    out.push({ start: cur[0].start, end: cur[cur.length - 1].end, text: cur.map((w) => w.text).join(' '), words: cur })
    cur = []
  }
  for (const w of words) {
    cur.push(w)
    if (/[.?!]$/.test(w.text) || w.end - cur[0].start > 12) flush()
  }
  flush()
  return out
}

/** Spoken and exported: not withheld, and no hard rule still broken after repair (a person can fix it). */
export const isPublished = (c: Cue) => c.tier !== 'never' && c.gate_failures.length === 0

export function playableCues(result: RunResult): Cue[] {
  return [...result.cues].filter(isPublished).sort((a, b) => a.start - b.start)
}

export function sentenceAt(list: Sentence[], t: number): Sentence | undefined {
  return list.find((s) => t >= s.start - 0.2 && t <= s.end + 0.4)
}

/** Split a sentence into plain and highlighted pieces around pointing phrases. */
export function highlightPointing(text: string, moments: Moment[]): { text: string; mark: boolean }[] {
  const phrases = moments.map((m) => m.phrase).filter(Boolean)
  if (!phrases.length) return [{ text, mark: false }]
  const escaped = phrases.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const re = new RegExp(`(${escaped.join('|')})`, 'gi')
  return text
    .split(re)
    .filter(Boolean)
    .map((piece) => ({ text: piece, mark: phrases.some((p) => p.toLowerCase() === piece.toLowerCase()) }))
}
