# Submission checklist

Event: [Nebius x NVIDIA Global AI Hackathon 2026](https://nebiusglobalaihackathon.devpost.com/). Rules rechecked:
**2026-10-26**. Deadline: **Fri Oct 30, 2026, 10:00 PDT / 20:00 Istanbul**; target submit by **16:00 Istanbul**.
Tick a box only with evidence.

## Official requirements → evidence

| Requirement (Rules) | Status | Evidence |
| --- | --- | --- |
| Runtime call to an NVIDIA open model through the Token Factory inference API | ✗ not met | no Token Factory inference call was made: the $25 credit was refused ("the event in your request was incorrect"), support is only on Discord (not accessible from Turkey), and the owner decided on 2026-10-30 to spend nothing. Every run used NVIDIA's API catalog; disclosed in README, Devpost text, site and video |
| Track: Best Apps and Agents, genuine attempt (multi-step workflow chaining tools) | ☑ | nine-stage pipeline, `backend/unsaid/pipeline.py` |
| Working demo URL, free and unrestricted until Dec 15 23:00 TRT | ☑ | [enesteve0.github.io/unsaid](https://enesteve0.github.io/unsaid/): static (recorded runs, evaluation), no server, no cost; monitor workflow checks it |
| Public repo with an OSI license visible in About | ☑ | public since 2026-10-29 as [enesteve0/unsaid](https://github.com/enesteve0/unsaid) after a clean gitleaks scan of all commits; GitHub detects MIT |
| README with setup and how NVIDIA models, Token Factory and other Nebius services are used | ☑ | `README.md` (results filled from `backend/eval/report.json`) |
| Public YouTube video under 3 minutes showing the project working | ☐ | `video/build/unsaid-demo.mp4` and captions ready (re-rendered 2026-10-30 with the catalog disclosure); owner uploads |
| Project description, built with, try-it links | ☑ | `docs/DEVPOST.md`, every placeholder filled; video URL added at upload |
| Feedback on Token Factory, AI Cloud and NVIDIA tools | ☑ | `FEEDBACK.md` (NVIDIA API catalog, Token Factory onboarding) |
| New project (after Aug 26, 2026) | ☑ | git history starts 2026-10-23 (docs), code from 2026-10-26; `docs/PROVENANCE.md` |
| English materials | ☑ | all |
| Third-party terms respected | ☑ | `NOTICE`, `samples/ATTRIBUTION.md`; NC-SA clips only used for metrics, not redistributed |

## Owner-only steps

- [ ] Token Factory account, card and API key → `.env` (`NEBIUS_API_KEY`); credit requests (Devpost form, Builders)
- [ ] Tavily key → `.env` (`TAVILY_API_KEY`), promo `BBDEVPOST`
- [ ] console.nebius.com billing ($25 activation) and `nebius profile create`
- [ ] Before Nov 25: Token Factory set to continue after the trial; Dec 1: pre-fund at least $35
- [ ] Fri: upload the video as **Public** on YouTube; paste the Devpost fields; tick the terms; Submit

## Release review (Thu Oct 29)

- [ ] `scripts/tf_day.sh`: smoke test, Token Factory samples, full evaluation; numbers synced into README, Devpost
      text and video
- [ ] Deployed build passes the judge path from a fresh browser (`/?judge=1`), a live 2-minute upload, Stop,
      exports; axe checks against the deployed URL
- [x] Secret scan of the tree and full history (`gitleaks` or equivalent) → repository public → renamed to
      `enesteve0/unsaid` → LICENSE detected in About (2026-10-29)
- [ ] `DEMO_URL` repository variable set so the monitor runs
- [ ] Tag `submission-2026-10-30`; record commit, URLs and access checks in `docs/PROVENANCE.md`
- [ ] After the deadline: change only environment configuration documented in the README
