// Speaks audio-description cues with the browser's speech synthesis.
// Handles the known pitfalls: voices load asynchronously, Chrome needs a user gesture before the first
// utterance, and `onend` occasionally never fires (a watchdog finishes the cue instead).

const PREFERRED = ['Ava', 'Samantha', 'Allison', 'Aria', 'Jenny', 'Google US English', 'Daniel', 'Serena', 'Karen']

export class Narrator {
  readonly available = typeof window !== 'undefined' && 'speechSynthesis' in window
  rate = 1.0
  private voice: SpeechSynthesisVoice | null = null
  private watchdog: number | undefined
  private primed = false
  private current: SpeechSynthesisUtterance | null = null

  constructor() {
    if (!this.available) return
    const pick = () => {
      const english = window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith('en'))
      this.voice =
        PREFERRED.map((name) => english.find((v) => v.name.includes(name))).find(Boolean) ?? english[0] ?? null
    }
    pick()
    window.speechSynthesis.addEventListener('voiceschanged', pick)
  }

  voices(): SpeechSynthesisVoice[] {
    if (!this.available) return []
    return window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith('en'))
  }

  setVoice(name: string) {
    this.voice = this.voices().find((v) => v.name === name) ?? this.voice
  }

  get voiceName() {
    return this.voice?.name ?? ''
  }

  /** Call from a click handler: unlocks speech in browsers that require a user gesture. */
  prime() {
    if (!this.available || this.primed) return
    const u = new SpeechSynthesisUtterance(' ')
    u.volume = 0
    window.speechSynthesis.speak(u)
    this.primed = true
  }

  speak(text: string, onEnd: () => void) {
    if (!this.available) {
      onEnd()
      return
    }
    this.cancel()
    const u = new SpeechSynthesisUtterance(text)
    if (this.voice) u.voice = this.voice
    u.rate = this.rate
    let finished = false
    const finish = () => {
      if (finished) return
      finished = true
      window.clearTimeout(this.watchdog)
      this.current = null
      onEnd()
    }
    u.onend = finish
    u.onerror = finish
    const words = text.split(/\s+/).length
    this.watchdog = window.setTimeout(() => {
      window.speechSynthesis.cancel()
      finish()
    }, ((words / 2.5) * 1.5 + 1) * 1000 / this.rate)
    this.current = u // keep a reference so the utterance is not garbage-collected mid-speech
    window.speechSynthesis.speak(u)
  }

  cancel() {
    if (!this.available) return
    window.clearTimeout(this.watchdog)
    if (this.current) {
      this.current.onend = null
      this.current.onerror = null
      this.current = null
    }
    window.speechSynthesis.cancel()
  }
}

export const narrator = new Narrator()
