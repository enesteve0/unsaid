# Devpost submission text (draft)

Fields marked `{{…}}` are filled from `backend/eval/report.json` and the deployed run before submitting. Nothing
else in this file may contain a number that is not measured.

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
- It describes what they point at **inside the pauses**, and never over the lecturer.
- Every description is **checked by code and re-checked against the frames**, and shows the evidence.
- It exports a WebVTT description track, captions, a transcript with descriptions inline, and Final Cut Pro markers.
- It suggests **the sentence the lecturer could say next time**, so the fix happens at the source.
- Long lectures run **overnight as a Nebius Serverless Job** with a dollar cap.

Try the 30-second test on the home page: hear a clip as a blind student does, then hear it with Unsaid.

## How we built it

Nine stages, four Nemotron models on Nebius Token Factory, each doing the one job it is best at:

1. **Listen:** NVIDIA Parakeet TDT 0.6B v2 (ONNX, CPU) transcribes with word timings and finds every silence. Super VL
   has no audio input, so this is how Unsaid knows when it may speak.
2. **Watch:** Nemotron 3.5 Super VL reads each segment as a low-frame-rate clip plus full-resolution stills, and returns
   strict JSON: slide text, charts with values, actions with times.
3. **Resolve:** Nemotron 3 Nano decides what each “this” or “here” actually points at. It rejects figures of speech,
   hypotheticals and phrases about time.
4. **Context:** Tavily reads the video’s own page and any works cited on slides, so names come from sources and never
   from faces.
5. **Understand:** Nemotron 3 Ultra reads the whole lecture in one context: the transcript, every segment report and
   every silence with its word budget. It decides what is visual-only and how important it is, and drafts each
   description to fit its pause.
6. **Write & fit:** code gates decide. A description must fit its silence (planned at 2.5 words per second, with guard
   bands) and must never overlap speech. It may use no number that isn’t printed on screen, no name without a source,
   and no “we see”. Nemotron 3.5 Lightning repairs failures; code trims; only essential facts may pause the video.
7. **Check:** Super VL judges every claim against frames from that moment (supported, contradicted or not visible),
   which sets each description’s tier: ready, needs review or withheld.
8. **Deliver:** tracks, transcript, markers and lecturer tips.

Every Token Factory call goes into a ledger with tokens, cached tokens, reasoning tokens, latency and cost. That
gives each video a price ({{usd_per_min}} per minute) and a counterfactual: the same text work on Ultra alone would
cost {{ultra_only_ratio}}× more.

## Results

On {{clips}} openly licensed lecture clips ({{minutes}} minutes, {{labels}} labelled pointing moments), compared with the
obvious one-shot approach (Super VL given the whole clip and the transcript):

| | One-shot | Unsaid |
| --- | --- | --- |
| Seconds spoken over the lecturer, per minute | {{oneshot.talk_over}} | {{unsaid.talk_over}} |
| Pointing moments covered | {{oneshot.coverage}} | {{unsaid.coverage}} |
| Descriptions with an invented number or name | {{oneshot.ungrounded}} | {{unsaid.ungrounded}} |
| Claims the frames do not support | {{oneshot.unsupported}} | {{unsaid.unsupported}} |
| Cost per video minute | {{oneshot.usd_per_min}} | {{unsaid.usd_per_min}} |

The Evaluation page lists where Unsaid still fails.

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
- **“This” is not always pointing.** “In the right polarity”, “at this point” and “students could look at the graph
  later” all match a naive lexicon; Nano filters them.

## Accomplishments that we're proud of

- Descriptions never talk over the lecturer: timing is enforced in code, not hoped for.
- Every description carries its evidence, and the interface itself passes automated WCAG 2.1 AA checks (axe) on
  every page.
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

nebius-token-factory, nebius-serverless, nvidia-nemotron, nemotron-3-ultra, nemotron-3.5-super-vl,
nemotron-3.5-lightning, nemotron-3-nano, nvidia-parakeet, onnxruntime, tavily, python, fastapi, pydantic, ffmpeg,
react, typescript, vite, playwright, axe-core, docker

## Additional info (for judges)

- **Track:** Best Apps and Agents
- **New or existing:** New. Started 2026-10-26.
- **Repository:** {{repo_url}} (MIT, LICENSE in About)
- **Demo:** {{demo_url}}. Testing instructions: open {{demo_url}}/?judge=1&code={{judge_code}} for the 30-second tour;
  the link also unlocks a reserved judging lane, so live runs never wait behind public traffic.
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
