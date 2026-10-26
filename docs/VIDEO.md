# Demo video plan

Target length 2:40–2:55, public YouTube, English. The first 30 seconds must work on their own: judges may watch
only the opening. Every number on screen comes from `backend/eval/report.json` or a recorded run of the deployed
build, never typed in by hand. No music; lecture excerpts are CC BY and credited in the description.

Voice: text-to-speech for narration (disclosed in the video description). The audio-description voice is a second,
clearly different voice so viewers can tell narration and description apart.

## Script

| Time | Picture | Sound |
| --- | --- | --- |
| 0:00–0:16 | Black. Small white text: *This is a lecture, as a blind student hears it.* | Lecture audio (engineerguy, Fourier machine): “…We use the values of these points as the inputs for the machine.” Silence. |
| 0:16–0:20 | Text: *Which points?* | — |
| 0:20–0:38 | Black. Same clip. Amber text appears in the pause as it is spoken. Title fades in: **Unsaid** | Lecture audio, then the description voice in the pause: the real cue from the deployed run. |
| 0:38–0:52 | Home page: the two buttons, the vermilion highlight on “these points”. | VO: “Lecturers point instead of speaking: as you can see, this curve, these points. Whatever they show stays unsaid. Unsaid finds those moments and describes them in the pauses, without ever talking over the lecture.” |
| 0:52–1:22 | Describe page: upload, queue, the nine stages lighting up with model names; then the timeline with amber cues slotted into silences. | VO: “Upload a lecture. NVIDIA Parakeet on Nebius transcribes it and finds every silence. Nemotron 3.5 Super VL watches each segment and reads the slides. Nemotron 3 Nano works out what each ‘this’ points at. Then Nemotron 3 Ultra reads the whole lecture at once on Nebius Token Factory, and plans what is unsaid and which pause it fits.” |
| 1:22–1:50 | Review cards: “fits the 5.6 s silence”, “every number is printed on screen”, claims checked against frames. | VO: “Models write; code decides. A description must fit its silence, never overlap speech, and use only numbers printed on screen and names from the screen, the speech or the video’s own page, which Tavily looks up. Nemotron 3.5 Lightning repairs anything that breaks a rule, and Super VL checks every claim against the frames again.” |
| 1:50–2:15 | Evaluation page: Unsaid vs one-shot baseline; then the failures list. | VO with the measured comparison from `report.json` (talk-over, coverage, invented numbers or names), then: “and we publish where Unsaid still fails.” |
| 2:15–2:32 | Models & cost tab; backlog digest. | VO: cost per minute of video and the Ultra-only counterfactual from the ledger; “long lectures run overnight as a Nebius Serverless Job with a dollar cap.” |
| 2:32–2:48 | Lecturer tips tab; end card. | VO: “And because the best description is the one the lecturer says aloud, Unsaid suggests the sentence to say next time. In presentation videos, 72% of what is shown is never properly described. Unsaid says it.” |
| 2:48–2:55 | End card: Unsaid · built with NVIDIA Nemotron on Nebius Token Factory · demo URL · GitHub. | — |

## Production

1. Generate narration per row with TTS; measure each clip’s duration.
2. Record the app with Playwright at 1920×1080 against the deployed URL, timing each interaction to its narration.
3. Render title and end cards as HTML in the app’s own type and colours.
4. Assemble with ffmpeg: picture tracks, narration, original lecture audio for the cold open, the description voice
   at the real cue time.
5. Run the finished video through Unsaid itself: upload its captions (SRT) to YouTube, so the demo is captioned by the
   product.
