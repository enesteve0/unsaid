# Unsaid — build checklist

Deadline: **Fri Oct 30, 2026 20:00 Istanbul** (submit by 16:00). Work directly on `master`. Items are checked only with evidence.

## Owner (identity-bound)

- [ ] Token Factory account + billing (Visa/MC, 3-D Secure), API key in `.env` as `NEBIUS_API_KEY`
- [ ] Credit requests: Devpost promo form + Builders Program
- [ ] Tavily key in `.env` as `TAVILY_API_KEY` (+ promo `BBDEVPOST`)
- [ ] Tue: console.nebius.com billing ($25 activation) + `nebius profile create`
- [ ] Fri: upload video to YouTube as **Public**; paste Devpost fields from `docs/DEVPOST.md`; Submit by 16:00 TRT

## Mon Oct 26 — foundation

- [ ] Memory + tasks files + provenance decision record + README status
- [ ] Backend scaffold (uv, Python 3.12, FastAPI) + `.env.example`
- [ ] `tf_client` (thinking control, defensive parsing, fallback chains, error policy) + `ledger` (prices, counterfactual)
- [ ] `gates` (overlap, fit, banned phrases, numbers, names) + unit tests
- [ ] `media` (probe, normalize, proxy clips, stills) + `deixis` lexicon + `segments` (gaps, slide changes)
- [ ] ASR prototype (Parakeet ONNX, word timestamps) on the Mac — package from verification agent
- [ ] Licensed sample clips downloaded with attribution — list from clip agent
- [ ] Prompt prototyping for Super VL / Ultra / Lightning / Nano (TF key, or build.nvidia.com locally only)

## Tue Oct 27 — end to end + gates

- [ ] TF smoke test (all four NVIDIA models) → `docs/EVIDENCE.md` (redacted)
- [ ] Pipeline end to end on 3 clips (perceive → resolve → bible → context → cues → verify → export)
- [ ] GATE 1 (18:00): strict JSON on 3 clips, ≥80% facts correct; Ultra bible <90 s on 60 s clip; ASR ≥5× real time
- [ ] GATE 2 (≤3 h, by 20:00): Nebius Serverless endpoint go/no-go (else Fly.io)

## Wed Oct 28 — product

- [ ] API + queue (per-session isolation, caps, judge lane, Stop, SSE progress)
- [ ] Web: Home A/B wow player, Run progress + ledger, Review timeline + editor, Exports, Tips
- [ ] Serverless Job: backlog + nightly eval with checkpoints and $ cap
- [ ] Eval set labels + first full eval run (B0, B1, Unsaid, ablations)
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

## Review

(filled in at the end: what shipped, measured results, what was cut)
