# Unsaid — build checklist

Deadline: **Fri Oct 30, 2026 20:00 Istanbul** (submit by 16:00). Work directly on `master`. Items are checked only with evidence.

## Owner (identity-bound)

- [ ] Token Factory account + billing (Visa/MC, 3-D Secure), API key in `.env` as `NEBIUS_API_KEY`
- [ ] Credit requests: Devpost promo form + Builders Program
- [ ] Tavily key in `.env` as `TAVILY_API_KEY` (+ promo `BBDEVPOST`)
- [ ] Tue: console.nebius.com billing ($25 activation) + `nebius profile create`
- [ ] Fri: upload video to YouTube as **Public**; paste Devpost fields from `docs/DEVPOST.md`; Submit by 16:00 TRT

## Mon Oct 26 — foundation

- [x] Memory + tasks files + provenance decision record + README status
- [x] Backend scaffold (uv, Python 3.12, FastAPI) + `.env.example`
- [x] `tf_client` (thinking control, defensive parsing, fallback chains, error policy) + `ledger` (prices, counterfactual)
- [x] `gates` (overlap, fit, banned phrases, numbers, names) + unit tests
- [x] `media` (probe, normalize, proxy clips, stills) + `deixis` lexicon + `segments` (gaps, slide changes)
- [x] ASR prototype (Parakeet ONNX, word timestamps) on the Mac — package from verification agent
- [x] Licensed sample clips downloaded with attribution — list from clip agent
- [x] Prompt prototyping for Super VL / Ultra / Lightning / Nano (TF key, or build.nvidia.com locally only)

## Tue Oct 27 — end to end + gates

- [ ] TF smoke test (all four NVIDIA models) → `docs/EVIDENCE.md` (redacted)
- [ ] Pipeline end to end on 3 clips (perceive → resolve → bible → context → cues → verify → export)
- [ ] GATE 1 (18:00): strict JSON on 3 clips, ≥80% facts correct; Ultra bible <90 s on 60 s clip; ASR ≥5× real time
- [ ] GATE 2 (≤3 h, by 20:00): Nebius Serverless endpoint go/no-go (else Fly.io)

## Wed Oct 28 — product

- [x] API + queue (per-session isolation, caps, judge lane, Stop, SSE progress)
- [x] Web: Home A/B wow player, Run progress + ledger, Review timeline + editor, Exports, Tips
- [x] Serverless Job code: backlog with checkpoints and $ cap (`batch/run_batch.py`); deploy pending AI Cloud account
- [x] Eval set: 6 clips, 21 builder labels; harness validated (prototype). [ ] Official run on Token Factory
- [ ] First deploy

## Thu Oct 29 — polish + publish

Status at 06:00: no `.env` yet (no Token Factory or Tavily key), Nebius CLI not installed, Fly not logged in,
Docker stopped. `a923416` (Oct 27, owner) committed the Oct 26 build-endpoint sample; its message describes a code
change it does not contain. That sample predates every quality fix and must be replaced by the Token Factory run.

Without keys (Claude):

- [x] PROVENANCE note on `a923416`; this plan
- [x] Nebius CLI 0.12.297 at `~/.nebius/bin/nebius` (shell config untouched); Fly.io fallback in `infra/fly/`
- [x] amd64 image builds with the current code (813 MB) and serves the app; the traversal request gets index.html
- [x] Independent reviews (pipeline; public demo security/robustness): all high and medium findings fixed with
      tests, except the backup-key race (no backup key is used) and running the container as non-root
- [x] Local QA: phone-width overflow fixed; "Title card shows title." now fails a gate; all 8 e2e tests pass
- [x] `scripts/fill_numbers.py`: Devpost/README numbers from `eval/report.json` and the sample ledger
- [x] Video draft re-rendered end to end (2:33 before the evaluation line): narration checked by ASR round trip;
      the cold open's paused description verified by transcription (no lecture word inside the pause); gallery
      JPEGs under 1 MB. Recording uses Playwright's own Chromium (Playwright 1.64 loses the system Chrome 156).
- [x] gitleaks (100 commits, no leaks) → public → renamed `enesteve0/unsaid` → description, topics, MIT detected

Night of Oct 29 (owner asleep; no money may be spent):

- [x] Keys: Tavily (free plan + `BBDEVPOST`, 9,000 credits) and Token Factory (owner added billing; balance $0.00, no
      trial credit visible) in `.env`, never displayed; Hugging Face write token in `.env` for deployment
- [x] No Token Factory inference until promo credit exists (only the free model listing was called)
- [x] Hugging Face Docker Spaces need PRO now → static demo on GitHub Pages: https://enesteve0.github.io/unsaid/
- [x] Official evaluation on the free API catalog (9 clips × 2, nothing skipped), numbers in README/Devpost/demo
- [x] Fourier example refreshed on the catalog (labelled); featured description checked against its frame
- [x] Video rendered (2:46, `video/build/unsaid-demo.mp4`) with Unsaid's own captions (`video/build/captions.srt`);
      gallery JPEGs and thumbnail ready. The pipeline scene's live run used the catalog; re-render after the Token
      Factory examples if credit arrives (`scripts/make_video.sh http://127.0.0.1:8080 https://enesteve0.github.io/unsaid`).

Morning (owner): fill nebius.com/promo-code (activation code `NEBIUS-DEVPOST-GLOBAL26`) → the emailed promo code goes
into Token Factory → Balance + → With promo code (Claude can enter it). Then `scripts/tf_day.sh` (smoke test and
the two examples on Token Factory, about $0.20 of credit) → `scripts/make_video.sh` → YouTube and Devpost.
If no credit arrives in time, the owner decides whether about $0.25 of Token Factory spend is acceptable: without
any Token Factory call, the entry does not meet the platform rule.

Key day, in order (owner steps marked **owner**):

1. **owner:** copy the Token Factory key, then `! printf 'NEBIUS_API_KEY=%s\n' "$(pbpaste)" >> .env`; the same for
   `TAVILY_API_KEY`. (`.env` already holds `PROVIDER=tokenfactory` and a random `JUDGE_CODE`, created Oct 29.)
   Claude checks the keys load without printing them.
2. `STEP=smoke scripts/tf_day.sh` (about 5 min) → `docs/EVIDENCE.md`. Stop and diagnose on any failure.
3. `STEP=samples scripts/tf_day.sh` (about 15 min). Check the hero cue against its frame (counts!) before choosing
   `--hero`; republish if needed; commit `samples/`.
4. `STEP=eval scripts/tf_day.sh` in the background (9 clips × 2 runs, 3 at a time; the report is saved after every
   clip).
5. Meanwhile, deploy. Nebius: **owner** billing at console.nebius.com, then
   `! ~/.nebius/bin/nebius profile create unsaid --endpoint api.nebius.cloud --federation-endpoint auth.nebius.com`
   (browser login); Claude runs `infra/nebius/create_secrets.sh` and `infra/nebius/deploy_endpoint.sh` with
   `PATH="$HOME/.nebius/bin:$PATH"` (the CLI is not on the shell's PATH, on purpose). Fallback:
   **owner** `! fly auth login`; Claude runs `infra/fly/deploy.sh`. Then the `DEMO_URL` repository variable and the
   repository homepage.
6. `python3 scripts/fill_numbers.py --demo-url <url>`; fill the opinion fields (rating, comparison, Nebius
   capabilities) from what was measured; FEEDBACK Token Factory section; commit; redeploy, so the image carries
   `backend/eval/report.json` (the Evaluation page reads it from the image).
7. Judge path on the deployed URL: `BASE_URL=<url> pnpm exec playwright test`, a live 2-minute upload in the judge
   lane, Stop, an edit, exports.
8. Video against the deployed URL: `DEMO_URL=<url> tts.py` → `record-video.mjs <url>` → `assemble.py`; watch it;
   **owner** uploads it to YouTube as Public, with Unsaid's own captions.
9. Gallery: `node scripts/gallery.mjs <url> ../video/build/gallery`. Thumbnail: put the Token Factory hero
   description verbatim into `video/cards/thumbnail.html` (it now quotes text no run produced) and re-render
   `thumbnail.png`. **owner** adds the images and pastes `docs/DEVPOST.md` into Devpost, then submits.
10. Tag `submission-2026-10-30`; submission record in `docs/PROVENANCE.md`.

- [ ] Design + accessibility pass (axe clean, keyboard, screen-reader semantics), judge tour
- [ ] Recorded fallback, kill switch, monitors, failure drill
- [ ] README, FEEDBACK.md, NOTICE, ARCHITECTURE/EVAL/FAILURES/DEVPOST docs
- [ ] Final eval from deployed build; numbers synced everywhere
- [ ] Secret + history scan → make repo public → rename to `enesteve0/unsaid` → LICENSE in About
- [ ] Demo video (scripted recordings + AI voiceover + captions/AD by Unsaid), ≤2:55

## Fri Oct 30 — submit

- [ ] Fresh-browser judge-path test on deployed URL
- [ ] Owner uploads video + submits; tag `submission-2026-10-30`; provenance updated; monitors running

## Progress notes

- 2026-10-26 evening: full pipeline runs end to end on real CC BY lectures (prototyped on build.nvidia.com locally;
  Token Factory runs pending the owner's key). Fourier excerpt with Ultra drafts: 7 cues, 5 inline, 6 auto,
  0.0 s talk-over, 6/6 visual pointing moments covered. Live path verified through the API (queue, SSE, result,
  session isolation). Web app passes axe WCAG 2.1 AA checks on every page. amd64 image builds (813 MB) and runs
  Parakeet inside the container. Video pipeline (Kokoro narration, Playwright scenes, ffmpeg assembly) produces a draft.
- 2026-10-26 late: added check-and-correct (Super VL finds unsupported claims, Lightning rewrites, code re-gates,
  Super VL re-checks; the frames outrank the plan), a motion clip for the verifier, judge-link unlocking, screen-reader
  output, backlog panel, evaluation small multiples (validated colours), failures list, smoke test, runbook
  (`scripts/tf_day.sh`), uptime monitor workflow, provenance table, thumbnail, gallery script. One-clip prototype
  (laser, build endpoint): talk-over 0 s vs 52 s one-shot; coverage 1.0 vs 0.5; unsupported 2/6 vs 3/6; 1 of 3
  flagged drafts corrected. gitleaks: no leaks. 49 backend tests, 6 e2e.
- 2026-10-26 midnight: the USGS clip's lost perception was transient build-endpoint 500s (identical requests pass
  when repeated). Client: a 5xx retries once after 5 s; a constrained 500 downgrades json_schema for 10 minutes, not
  for good; every call streams, and timeouts bound the silence between chunks (vision 60 s), so a stall costs about a
  minute instead of 180 s. Ultra's running token count shows during planning. `REASON_EFFORT=medium` (chat template
  `medium_effort`) halved Ultra's reasoning on a test prompt; six-clip comparison against full effort pending.
  FEEDBACK item on json_schema withdrawn (it was intermittent) and replaced with measured findings. 53 backend tests,
  7 e2e.
- 2026-10-27 early morning (build-endpoint prototype; official numbers come from Token Factory):
  - Effort: same code and inputs, coverage 0.33 at full and at medium effort; medium used 58% fewer Ultra tokens.
    Medium is now the default.
  - Coverage (0.33 vs 0.53 one-shot) is the weak number. `eval/diagnose.py` traces each label. Losses fixed:
    - paused descriptions placed when a fact first appeared, up to 16 s before the pointing;
    - inline descriptions put in a silence far from the moment;
    - pointing facts written as the spoken gist and dropped as "already spoken" (planner prompt, 6/8 vs 4/8 on
      targeted moments);
    - perception losing the moment frames;
    - several moment ids in one field.
  - Quality fixes:
    - the corrector never saw what the checker observed ("rock bars adjusted");
    - checks used frames from after a description was heard;
    - the word budget ignored punctuation pauses (7 of 17 drafts);
    - the writer never saw printed values;
    - spelled-out numbers bypassed the gate;
    - extended descriptions had no 30-word limit;
    - tips repeated contradicted facts;
    - the editor refused chart values.
  - Evaluation hygiene: prompt examples that came from the evaluation clips were replaced (Resolve recall 42/48 vs
    41/48), the report says the prompts were developed on these clips, and the held-out split is supported.
  - 72 backend tests, 8 e2e.
- Development clips, prototype on the build endpoint, medium effort:

  | | Before tonight | After the fixes | Pause waits for the picture |
  | --- | --- | --- | --- |
  | Coverage (one-shot) | 0.33 (0.54) | 0.45 (0.58) | 0.50 (0.68) |
  | Unsupported claims | 0% | 17% | 19% |
  | Invented numbers or names | 0% | 6% | 0% |
  | Pauses per minute | 1.00 | 1.27 | 1.55 |

  - Unsupported rose because the frame check became strict about timing; every remaining flag is a pause describing
    a pointer position the checker cannot confirm.
  - Run-to-run noise is about ±0.1 in coverage (the one-shot moved 0.58 → 0.68 with identical inputs). Tuning on
    the six development clips is frozen except for bugs; the official run pools two runs per clip (`--repeat 2`).
- Known gaps (low impact, from the data-flow review):
  - Ultra's style notes are unused;
  - the timing estimate counts maths symbols as one word;
  - check frames are capped at three;
  - event times relative to the clip are guessed;
  - Tavily's cited-work title is not passed to the writer.
- Held-out clips (added 2026-10-27, labelled blind): the phrase detector missed 4 of their 17 pointing moments
  ("here" followed by more words; nouns such as "variations" that are not in its list). Do not tune the detector
  or prompts on these clips before the official run; that would turn them into development clips.
- TF day checks:
  - smoke test (perception shape, `medium_effort` honoured);
  - measure a live 2-minute run and set the Describe page's "a couple of minutes" to the measured time;
  - official evaluation with held-out clips.
- Blocked on owner: NEBIUS_API_KEY (Token Factory), TAVILY_API_KEY, Nebius AI Cloud account for Serverless.

## Review

(filled in at the end: what shipped, measured results, what was cut)
