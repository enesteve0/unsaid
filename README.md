# Unsaid

**Audio description for everything a lecture shows but never says.**

Lecturers point instead of speaking: *“…and as you can see, this curve tells us everything.”* A blind or low-vision
student hears the sentence but never learns what the curve shows. Unsaid watches a lecture video, finds the moments
where the speech relies on the picture, and describes what is unsaid in the pauses, without ever talking over the
lecturer. It runs on NVIDIA Nemotron models served by **Nebius Token Factory**, with NVIDIA Parakeet speech recognition
on CPU and an overnight backlog job built for **Nebius Serverless Jobs**.

Built for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/), *Best Apps and Agents* track.

| | |
| --- | --- |
| Live demo | _added at submission_ |
| Demo video | _added at submission_ |
| License | [MIT](LICENSE) for the code. Models and media keep their own licenses; see [Credits](#credits). |

## What it does

1. **Hear the gap.** On the home page, play a lecture clip twice: once as a blind student hears it (picture off),
   once with Unsaid. The description arrives in the pause after “these points”, not over the lecturer.
2. **Describe your own clip.** Upload up to three minutes of lecture video. You see every stage, the model behind it
   and its cost, and you can stop at any time.
3. **Review with evidence.** Each description shows the checks it passed: it fits its silence, never overlaps speech,
   uses only numbers printed on screen and names found on screen, in the speech or on the video’s own page, and every
   claim was checked again against the frames.
4. **Publish.** Download a WebVTT `kind="descriptions"` track, captions, a transcript with descriptions inline,
   Final Cut Pro markers, or everything as JSON.
5. **Fix it at the source.** For each pointing moment, Unsaid suggests a sentence the lecturer could say next time so
   the words carry the picture (W3C calls this integrated description).
6. **Run the backlog overnight.** A batch job, built for Nebius Serverless Jobs, describes a whole playlist, resumes where it stopped,
   respects a dollar cap and leaves a digest: how many lectures are ready and how many need a person.

## How it works

```
lecture.mp4
  │
  ├─ Listen      NVIDIA Parakeet TDT 0.6B v2 (ONNX, CPU): words with timings, speech, silences
  ├─ Segment     code: slide changes; pointing phrases ("as you can see", "this curve", "over here")
  ├─ Watch       Nemotron 3.5 Super VL: each segment as a low-fps clip + full-resolution stills → JSON facts
  ├─ Resolve     Nemotron 3 Nano: does each "this" point at something visible? what is unsaid?
  ├─ Context     Tavily: names from the video's own page and works cited on slides (never from faces)
  ├─ Understand  Nemotron 3 Ultra: the whole lecture in one context; what is visual-only, how important,
  │              which silence it fits, and a draft within that silence's word budget
  ├─ Write & fit code gates; Nemotron 3.5 Lightning repairs drafts that break a rule; code trims, or pauses for essentials
  ├─ Check       Nemotron 3.5 Super VL: every claim re-checked against frames from that moment;
  │              Lightning corrects what it flags, code re-gates, Super VL checks once more
  └─ Deliver     tracks, transcript, editor markers, lecturer tips (Nemotron 3.5 Lightning)
```

### Why four Nemotron models

| Model (Token Factory ID) | Job in Unsaid | Why this one |
| --- | --- | --- |
| Nemotron 3.5 Super VL (`nvidia/Nemotron-3.5-Super-VL`) | Watch every segment; verify every description | The only model here that sees images and video. Thinking off: this is perception. |
| Nemotron 3 Ultra (`nvidia/Nemotron-3-Ultra-550b-a55b`) | Plan the whole lecture and draft each description | Needs the entire transcript, every segment report and every silence at once (1M-token context). Thinking on, streamed. One call per video. |
| Nemotron 3.5 Lightning (`nvidia/Nemotron-3_5-Lightning`) | Repair descriptions that fail a rule or the frame check; lecturer tips | Many small, latency-sensitive rewrites, in parallel. |
| Nemotron 3 Nano (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) | Classify pointing phrases | High-volume structured classification with strict JSON. |

Every call is written to a ledger with tokens, cached tokens, reasoning tokens, latency and dollar cost at Token
Factory list prices, next to what the same text work would have cost on Ultra alone. The app shows it per video.

### Rules enforced in code

Models write; code decides. A description is used only if:

- it starts inside a silence and finishes before speech resumes (150 ms guard on both sides, 300 ms synthesis
  lead-in), planned at 2.5 words per second, slower than normal speech, plus a short pause at each comma, colon or
  dash;
- a description of something the speaker points at starts between 3 s before and 10 s after the pointing, and not
  before the thing is on screen;
- it contains no number that is not printed on screen or spoken, and no name that is not on screen, in the speech
  or on the video’s page (fetched with Tavily);
- it avoids “we see”, “the image shows” and “in this video”; hedges and past tense are flagged for review;
- if nothing fits, it becomes an extended description of at most 30 words (the player pauses the video at the end of
  the speaker's sentence, WCAG 2.1 SC 1.2.7), but only for facts Ultra marked essential or that the speaker points at,
  and never in the middle of another description. Anything else is left out rather than squeezed into a fragment;
- it says what the picture shows, not only what kind of picture it is ("Title card shows title." fails);
- a description that identifies a person without a source is withheld, and one that still breaks a rule after two
  repairs is held back: it is not spoken or exported until a person fixes it in the editor, where the same checks
  run again.

## Results

<!-- results:start -->
Measured on Nebius Token Factory before submission (`scripts/tf_day.sh`); the app's Evaluation page shows the
method, both clip sets and the failure list.
<!-- results:end -->

## Where Nebius Token Factory accelerated the work

- **One API, four model sizes.** Routing each step to the right Nemotron size was a configuration change, not four
  integrations. Model chains live in environment variables with fallbacks
  (Ultra → Nemotron 3 Super → Super VL; Lightning ↔ Nano) and are audited against `/v1/models?verbose=true` at boot.
- **Structured output.** Strict `json_schema` decoding plus the schema in the prompt and pydantic validation; if a
  constrained request fails with a server error, the client retries with the schema in the prompt only and keeps that
  model unconstrained for ten minutes.
- **Reasoning control.** `chat_template_kwargs.enable_thinking=false` for perception and rewrites; Ultra thinks with
  an explicit budget. Every call streams, so gateways never see an idle connection, a stalled call is cut off after
  a minute without a chunk, and the app shows Ultra's running token count while it plans.
- **Prompt caching.** Stable instruction prefixes; cached tokens are shown in the ledger.
- **Resilience built for the API's behaviour.** 402 switches the app to clearly labelled recorded runs; 401/403
  tries a backup key; 404/409/410 retires a model; 429 honours Retry-After once; 5xx and timeouts retry once, then
  open a short circuit breaker.

## Quickstart (local)

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 with pnpm, ffmpeg.

```bash
git clone https://github.com/enesteve0/unsaid && cd unsaid
cp .env.example .env            # add NEBIUS_API_KEY (Token Factory) and TAVILY_API_KEY
cd web && pnpm install && pnpm build && cd ..
cd backend && uv sync
uv run python -m unsaid.cli describe ../samples/fourier-machine/video.mp4 --out data/try   # command line
uv run python -c "from unsaid.api import main; main()"                                       # web app on :8080
```

The first run downloads NVIDIA Parakeet (int8, about 630 MB) into `backend/models/`.

Tests: `cd backend && uv run pytest` (no keys needed; Token Factory is mocked) and
`cd web && pnpm exec playwright test` (WCAG 2.1 AA checks with axe against a running server).

## Deploy on Nebius

```bash
# once: Nebius CLI >= 0.12.277, `nebius profile create`, a project in eu-west1 (non-GPU quota by default)
export PROJECT_ID=<your eu-west1 project id>
infra/nebius/create_secrets.sh            # API keys from .env into Nebius SecretStash
infra/nebius/deploy_endpoint.sh           # build linux/amd64, push to Container Registry, create or restart the endpoint
```

The endpoint runs on `cpu-d3` with an explicit preset and a 20 GiB disk; the CLI defaults (H100/H200 GPU, 250 GiB)
are never used. The backlog job uses the same image:

```bash
nebius ai job create --name unsaid-backlog --image <image> --platform cpu-d3 --preset 4vcpu-16gb --disk-size 20Gi \
  --timeout 1h --restart-policy never \
  --container-command "uv run --no-sync python -m batch.run_batch --mode backlog --out /out --budget-usd 2" \
  --env-secret NEBIUS_API_KEY=unsaid-secrets --volume s3://<bucket>:/out:rw
```

## Operations (judging period)

- Free, public, no sign-up. Each browser gets its own runs. Examples load instantly.
- An access code (in the Devpost testing instructions) opens the judges' lane: a run slot that public runs never
  use, and its own budget.
- Public lane: one live run at a time per browser or address, 3 per browser per 10 minutes, 5 per address per hour;
  a visible queue, never a single-user lock.
- Daily and monthly spend caps. Every queued or running run reserves an estimate against them, and failed or
  stopped runs are charged for the calls they made.
- If the models keep failing, public live runs pause for ten minutes while the judges' lane keeps trying; if
  Token Factory credit runs out or a key is rejected, all live runs pause. The clearly labelled recorded examples
  always remain, and `DEMO_MODE=recorded` does the same on purpose.
- Uploaded videos, and the audio, clips and frames taken from them, are deleted after 24 hours.

## Limitations

- Descriptions are drafts with evidence, not a replacement for professional describers. Anything marked “needs
  review” should be checked by a person before publishing.
- English only: the Nemotron models used here do not support other languages yet.
- Mathematical notation is read as printed; complex derivations need a human describer.
- Live runs take clips up to 3 minutes; longer lectures go to the overnight backlog.
- Browser speech voices differ by operating system; the WebVTT track works with any player that supports
  description tracks.

## Prior work

Unsaid builds on *Say It All* (Peng et al., CHI 2021: 72% of 610 visual elements in 90 presentation videos were
insufficiently described), *Slidecho* (ASSETS 2021), *VeasyGuide* (ASSETS 2025) and *Deictic* (2026, resolving “this”
in lecture captions). Commercial AI audio description (ViddyScribe, 3Play Media, Verbit, YuJa) describes scenes;
Unsaid focuses on the moments the speech points at, enforces timing and grounding in code, and shows its costs.

## Credits

- Models: NVIDIA Nemotron 3 Ultra, Nemotron 3.5 Super VL and Nemotron 3.5 Lightning (OpenMDW-1.1) and Nemotron 3 Nano
  (NVIDIA Nemotron Open Model License) via Nebius Token Factory. NVIDIA Parakeet TDT 0.6B v2 (CC-BY-4.0) through
  [onnx-asr](https://github.com/istupakov/onnx-asr) (MIT). Silero VAD (MIT). See [NOTICE](NOTICE).
- Web search: [Tavily](https://tavily.com).
- Typefaces: Atkinson Hyperlegible Next by the Braille Institute, Instrument Serif and IBM Plex Mono (all OFL).
- Example videos: see [samples/ATTRIBUTION.md](samples/ATTRIBUTION.md).

Research notes, the submission checklist and decision records are in [docs/](docs/).
