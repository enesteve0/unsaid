# Devpost submission text

Template for `docs/DEVPOST.md`. `scripts/fill_numbers.py` fills every `{{…}}` from `backend/eval/report.json` (the
evaluation) and `samples/fourier-machine/result.json` (the home-page run). Nothing else in this file may contain a
number that is not measured. Edit this template, not the generated file.

## Project overview

**Project name (≤60):** Unsaid

**Elevator pitch (≤200):** Lecturers say “as you can see” and blind students can’t. Unsaid finds those moments and
describes them in the pauses, never over the lecturer, using four NVIDIA Nemotron models on Nebius.

## About the project

## Inspiration

Watch a lecture with your eyes closed. *“…and as you can see, this curve tells us everything.”* Which curve? Lecturers
point instead of speaking all the time, and in a study of 90 presentation videos, 72% of 610 visual elements were
insufficiently described by the speaker (Peng et al., CHI 2021). For a blind or low-vision student, every one of those
moments is a gap in the lesson. Audio description fills such gaps, and WCAG 2.1 AA requires it for prerecorded video:
US public universities must comply from April 2027. But description is slow and expensive, and existing AI tools
describe *scenes*, not the moment a lecturer says “this”.

## What it does

Unsaid takes a lecture video and returns an audio-description track for what the picture shows but the speech never
says:

- It finds **pointing moments**: “as you can see”, “these points”, “over here”.
- It describes what they point at **in the lecturer's pauses**, pauses the video when no pause is long enough, and
  never speaks over the lecturer.
- Every description is **checked by code and re-checked against the frames**, and shows the evidence.
- It exports a WebVTT description track, captions, a transcript with descriptions inline, and Final Cut Pro markers.
- It suggests **the sentence the lecturer could say next time**, so the fix happens at the source.
- {{backlog_line}}

Try the 30-second test on the home page: hear a clip as a blind student does, then hear it with Unsaid.

## How we built it

Nine stages, four Nemotron models on Nebius Token Factory, each doing the one job it is best at:

1. **Listen:** NVIDIA Parakeet TDT 0.6B v2 (ONNX, CPU) transcribes with word timings and finds every silence. Super VL
   has no audio input, so this is how Unsaid knows when it may speak.
2. **Segment:** code splits the video at slide changes and flags pointing phrases (“as you can see”, “this curve”).
3. **Watch:** Nemotron 3.5 Super VL reads each segment as a low-frame-rate clip plus full-resolution stills, and returns
   strict JSON: slide text, charts with values, actions with times.
4. **Resolve:** Nemotron 3 Nano decides what each “this” or “here” actually points at. It rejects figures of speech,
   hypotheticals and phrases about time.
5. **Context:** Tavily reads the video’s own page and any works cited on slides, so names come from sources and never
   from faces.
6. **Understand:** Nemotron 3 Ultra reads the whole lecture in one context: the transcript, every segment report and
   every silence with its word budget. It decides what is visual-only and how important it is, and drafts each
   description to fit its pause.
7. **Write & fit:** code gates decide. A description must fit its silence (planned at 2.5 words per second, with guard
   bands) and must never overlap speech. It may use no number that isn’t printed on screen, no name without a source,
   and no “we see”. Nemotron 3.5 Lightning repairs failures; code trims; only essential facts may pause the video.
8. **Check:** Super VL judges every claim against frames from that moment (supported, contradicted or not visible),
   which sets each description’s tier: ready, needs review or withheld.
9. **Deliver:** tracks, transcript, markers and lecturer tips.

Every Token Factory call goes into a ledger with tokens, cached tokens, reasoning tokens, latency and cost. That
gives each video a price ({{usd_per_min}} per minute of video in the evaluation) and a counterfactual: the same text
work on Ultra alone would cost {{ultra_only_phrase}}.

## Results

On {{clips}} openly licensed lecture clips ({{minutes}} minutes, {{labels}} labelled pointing moments), each described
{{runs}}, measured {{eval_where}}, compared with the obvious one-shot approach (Super VL given the whole clip and the timed transcript,
asked to place descriptions in pauses):

- **Spoken over the lecturer:** Unsaid {{unsaid.talk_over}} per minute of video; one-shot {{oneshot.talk_over}}.
- **Descriptions that fit in a pause:** Unsaid {{unsaid.in_silence}}; one-shot {{oneshot.in_silence}}.
- **Pointing moments covered:** Unsaid {{unsaid.coverage}}; one-shot {{oneshot.coverage}}.
- **Descriptions with an invented number or name:** Unsaid {{unsaid.ungrounded}}; one-shot {{oneshot.ungrounded}}.
- **Claims the frames do not support:** Unsaid {{unsaid.unsupported}}; one-shot {{oneshot.unsupported}}.
- **Video pauses for extended descriptions:** Unsaid {{unsaid.pauses}} per minute; one-shot {{oneshot.pauses}}.
- **Model cost per minute of video:** Unsaid {{unsaid.usd_per_min}}; one-shot {{oneshot.usd_per_min}}.

{{coverage_sentence}} One caveat: unsupported claims are scored by the same Super VL verifier that Unsaid's own
check step answers to, so that row favours Unsaid; invented numbers and names are counted by code.

{{dev_clips_word}} of the clips were also used to develop Unsaid's prompts. The other {{heldout_clips}} were labelled blind
and never used to tune them (Unsaid ran on them once, before one later change to where paused descriptions start), and
their labels include pointing moments our phrase detector misses. {{heldout_sentence}} The Evaluation page reports both
sets separately and lists where Unsaid still fails. No phrase from any clip appears in a prompt.

## Challenges we ran into

- **Super VL has no audio.** We added NVIDIA Parakeet on CPU to know when the lecturer speaks; descriptions are timed
  against its speech intervals.
- **Fitting a description into 2.4 seconds.** A free-writing model overshoots. Moving the draft into Ultra’s plan,
  where every silence has a word budget, cut extended (pausing) descriptions from 6 of 8 to 2 of 7 on our first test
  lecture.
- **Thinking models and budgets.** Nemotron thinks by default. A small budget returns empty content, and long
  non-streamed reasoning calls hit gateway timeouts. We switch thinking off where it isn’t needed, give Ultra an
  explicit budget, and stream it.
- **Structured output that sometimes isn’t.** We send the schema in the prompt as well as through constrained
  decoding, validate it with pydantic, and repair or retry. Truncated JSON gets more room instead of a “repair”.
- **Counting, and a checker that could only delete.** Super VL can read twenty sampled points as “bars 0 through 10
  and 11 through 20”, and Ultra turns that into “11 at 10, 9 at zero” (the frame shows ten and ten). On one run the
  frame check caught it, but the corrector was never shown what the checker saw, so all it could do was delete: the
  description became “rock bars adjusted”. Passing the observation through fixed that, and a correction may no
  longer shrink a description to a fragment. On another run the check passed the wrong count. Code cannot catch a
  plausible count, so the Evaluation page lists such failures and tiers mark what a person should check.
- **Requests that never answer.** A few requests hung until the client gave up. Every call now streams, so a stall
  is cut off after a minute without a chunk instead of after a three-minute budget.
- **“This” is not always pointing.** “In the right polarity”, “at this point” and “students could look at the graph
  later” all match a naive lexicon; Nano filters them.

## Accomplishments that we're proud of

- Descriptions never talk over the lecturer: timing is enforced in code, not hoped for.
- Every description carries its evidence, and the interface itself passes automated WCAG 2.1 AA checks (axe) on
  every page, works by keyboard, and reflows on a 320-pixel screen.
- A complete product: try it live, review, edit with the same checks, export, and run overnight.

## What we learned

The most valuable model call is often the one that holds the whole problem at once. Ultra planning the lecture as a
whole beat any number of local rewrites. Cheap models are best at repair, not authorship. And the best accessibility
fix happens before the recording, which is why Unsaid coaches the lecturer.

## What's next

- Reviewer edits become cached examples for the planner and feed a data flywheel.
- More languages, as Nemotron adds them.
- An LMS integration (Canvas, Moodle) so the backlog job runs on every new upload.
- A pilot with a university accessibility office before the April 2027 deadline.

## Built with

nebius-token-factory, {{hosting_tags}}nvidia-nemotron, nemotron-3-ultra, nemotron-3.5-super-vl,
nemotron-3.5-lightning, nemotron-3-nano, nvidia-parakeet, onnxruntime, tavily, python, fastapi, pydantic, ffmpeg,
react, typescript, vite, playwright, axe-core, docker

## Additional info (for judges)

- **Track:** Best Apps and Agents
- **New or existing:** New. Started 2026-10-26.
- **Repository:** {{repo_url}} (MIT, LICENSE in About)
- **Demo:** {{demo_url}}. Testing instructions: open {{demo_url}}/?judge=1 for the 30-second tour. The hosted demo is
  a static site with the recorded Token Factory runs, every check and the evaluation: it has no server, so it stays
  up through judging at no cost. Describing a new clip needs the full app: clone the repository, add a Token Factory
  key and run it (README, Quickstart); the video shows a live run end to end.
- **Models and why:** see “How we built it”.
  - Super VL is the only vision model.
  - Ultra is used once per video, for whole-lecture judgement over a 1M-token context.
  - Lightning handles cheap parallel repairs.
  - Nano handles strict-JSON classification.
  - Measured split of cost: {{cost_split}}.
- **Nemotron output quality:** {{rating}}/10.
  - Strongest: Ultra’s whole-lecture planning and Super VL’s reading of slides and charts.
  - Weakest: free-writing to a word budget, and occasional truncated or malformed JSON.
- **Approach:** prompt engineering, structured outputs and routing; no fine-tuning (Token Factory doesn’t offer
  self-service Nemotron fine-tuning).
- **Compared with other models:** {{comparison}}.
- **Most valuable Nebius capabilities:** {{nebius_capabilities}}.
- **Recommend Nemotron on Nebius:** {{recommend}}/10. **Experience vs other clouds:** {{experience}}/10.
- **Improvements we’d like:** see FEEDBACK.md.
- **Hopes for the Nemotron team:** see FEEDBACK.md.
- **Tavily:** Yes. Runtime `extract` on the video’s source page and `search` for citations on slides; request ids are
  stored with each run and shown in the app.
- **IRL city:** none.
- **AI tools used:** Claude Code (Anthropic) for implementation, under the owner’s direction.
