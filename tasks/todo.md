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
- Blocked on owner: NEBIUS_API_KEY (Token Factory), TAVILY_API_KEY, Nebius AI Cloud account for Serverless.

## Review

(filled in at the end: what shipped, measured results, what was cut)
