# Provenance and decisions

## Initial baseline

- Research date: 2026-10-23.
- Initial contents: original research summaries, checklists and repository configuration only.
- Imported application code, models, datasets and assets: none.
- Initial foundation preparation was AI-assisted; factual requirements are linked to official sources in the research report. The owner remains responsible for verifying any generated work.

## Decisions

- Keep this workspace private until the owner separately instructs publication.
- Recheck work-period restrictions before implementation.
- Preserve third-party attribution and distinguish existing work from competition-period contributions.
- Do not assume that an event permits identical submissions to other hackathons.

### 2026-10-26: product, track and workflow

- **Product:** *Unsaid*, audio description for what lecture videos show but never say. It is a new project, started on 2026-10-26, inside the submission period (Aug 26 – Oct 30, 2026). It reuses no code from any other project or hackathon.
- **Track:** Best Apps and Agents.
  - Coding was rejected because it depends on Token Factory Sandboxes beta access.
  - Physical AI was rejected because there is no hardware.
  - Personal AI was rejected because of the risk of hosting it and keeping judge access open.
- **Why:** deep research on 2026-10-26 (official rules, FAQ, updates, Token Factory catalog, judge criteria), followed by a three-perspective review of seven candidate concepts. Unsaid ranked first on technical depth and impact, and it needs no physical fieldwork.
- **Platform:** NVIDIA Nemotron models are called at runtime through Nebius Token Factory (`https://api.tokenfactory.nebius.com/v1/`):
  - Nemotron 3.5 Super VL
  - Nemotron 3 Ultra
  - Nemotron 3.5 Lightning
  - Nemotron 3 Nano

  NVIDIA Parakeet speech recognition runs on CPU. The planned hosts are a Nebius Serverless Endpoint and a Serverless Job, pending a go/no-go check on 2026-10-27.
- **Workflow (owner instruction, 2026-10-26):** commit and push directly to `master`, with no feature branches or pull requests. Commit messages carry no co-author or AI-attribution lines. This replaces the branch/PR workflow described in CONTRIBUTING.md.
- **Publication (owner instruction, 2026-10-26):** the repository may be made public on 2026-10-29, after a clean scan for secrets across the working tree and the full history. Until then it stays private.
- **AI assistance:** the application is being built with an AI coding assistant (Claude Code). The owner directs and reviews the work.

### 2026-10-29: note on commit `a923416`

`a923416` (2026-10-27 15:07) adds `samples/fourier-machine/` and `samples/manifest.json`. They are the home-page
example from a prototype run on build.nvidia.com on 2026-10-26 (`"provider": "nvidia_build"` in `result.json`),
made before the quality fixes of 2026-10-27. The commit changes no code. Its message describes a fix to pause
behaviour informed by held-out failures, but the commit contains no such change. The real change to where paused
descriptions start is `b10c380`. It was found on the laser development clip, and its message and the evaluation
report both disclose the single prototype run on the held-out clips that came before it. The example is replaced
by a Token Factory run before submission.

### 2026-10-29: publication

- Before publishing, gitleaks 8.30.1 scanned all 100 commits on every ref and found no leaks. A pattern search of
  the tracked files for API-key formats (NVIDIA, Tavily, OpenAI-style, GitHub, AWS) found none. The only private
  detail in the history is a local font path in an earlier version of `video/cards/thumbnail.html`, which shows the
  builder's macOS user name. It is not a credential, and the current file uses relative paths.
- The repository was renamed from `enesteve0/nebius-nvidia-global-ai-hackathon-2026` to `enesteve0/unsaid` (the
  old URL redirects) and made public on the morning of 2026-10-29, as the owner had authorized.
  GitHub detects the MIT license.
- Before publication, two independent reviews (the pipeline, and the public demo's security and robustness) led
  to the fixes in the commits of 2026-10-29. The most serious was that the web route could serve files outside
  the built app. The app had never been deployed publicly.

### 2026-10-29: no spend, a static demo, and the evaluation on the API catalog

- **Owner constraint:** no money may be spent on model inference or hosting.
- **Credentials:** with the owner signed in to each site in their browser, Claude created a Token Factory API key
  (`unsaid-hackathon`), a Hugging Face write token (`unsaid-deploy`) and used the existing Tavily key. Each went from
  the page into the gitignored `.env` by clipboard or script, without being displayed. The owner entered the
  Token Factory billing details and card. Claude entered no personal or payment data, and accepted no terms.
- **Token Factory credit:** after billing setup, the account showed a balance of $0.00 and no October
  transactions, so no trial credit was visible. The hackathon's code `NEBIUS-DEVPOST-GLOBAL26` is an
  activation code for the promo-code form linked from the Devpost resources page. Entered as a promo code in the
  console, it is rejected. The form needs the owner's personal details, so it is the owner's step. It works only
  from that link, which carries the event and activation code: on Oct 30 the bare nebius.com/promo-code URL, which
  Claude had opened, ended in "no event name found". Reopened from the Devpost link, the form has the event set;
  submitted from there, it was answered by email that the code "could not be issued because the event in your
  request was incorrect". The FAQ sends credit problems to the Nebius Discord, which is not accessible from Turkey.
- **Owner decision, 2026-10-30, about 12:45 TRT: no Token Factory spend at all.** Offered a run of about 15 cents, then four
  capped calls of about $0.0001, the owner chose "strictly zero calls", after being shown the FAQ answer that NVIDIA
  models through another provider do not satisfy the platform rule. Consequences, all disclosed: no Token Factory
  inference call; every run (example, evaluation, video) is from NVIDIA's API catalog, with Nemotron 3.5 Lightning
  standing in for Nano; the README, Devpost text, site footer and About page, video narration, end card and
  thumbnail say so; `docs/SUBMISSION.md` marks the runtime-call requirement as not met. Until promo credit exists, no Token
  Factory inference call is made. Listing models, which is free, confirmed the key and all five NVIDIA models.
- **Tavily:** free plan, plus the `BBDEVPOST` coupon (8,000 credits). No card.
- **Evaluation:** run on NVIDIA's API catalog (build.nvidia.com) with the same Nemotron models, at no cost, as the
  owner chose. Calls are priced at Token Factory list prices. The report, README and Devpost text say where it
  ran, and that classification used Lightning there, because the catalog account has no Nano.
- **Hosting:** Hugging Face now requires a paid plan for Docker Spaces (`402: ... requires a PRO subscription`);
  nothing was created. The demo is a static site on GitHub Pages (recorded runs, no server, no spend), deployed
  from `master` by a workflow, with no extra branch. Live describing runs from the repository with one's own key.
  Scripts for a live host (Nebius endpoint, Fly.io) stay in `infra/` for anyone willing to pay.
- **Judging period:** recorded examples only, as the owner chose. A live host, if one is ever used, can open live
  runs to judges only (`PUBLIC_LIVE=false`) and stop on a date (`LIVE_UNTIL`).

## Recording future work

For every imported component, record its upstream URL, immutable commit/version, license, purpose and changes. For every material project decision, record date, rationale and source. If a baseline project is reused, identify its pre-event commit and explain the event-period work separately.

### Third-party components and media

Exact versions are pinned in `backend/uv.lock` and `web/pnpm-lock.yaml`. None of this code was modified.

| Component | Version / source | License | Purpose |
| --- | --- | --- | --- |
| NVIDIA Nemotron 3 Ultra, 3.5 Super VL, 3.5 Lightning | Nebius Token Factory API | OpenMDW-1.1 | planning, perception and checking, repairs |
| NVIDIA Nemotron 3 Nano | Nebius Token Factory API | NVIDIA Nemotron Open Model License | pointing-phrase classification |
| NVIDIA Parakeet TDT 0.6B v2 (int8 ONNX, `istupakov/parakeet-tdt-0.6b-v2-onnx`) | downloaded at build time | CC-BY-4.0 | speech recognition |
| Silero VAD (ONNX, `istupakov/silero-vad-onnx`) | downloaded at build time | MIT | speech segments |
| onnx-asr / onnxruntime | 0.12.0 / 1.31.0 | MIT / MIT | running the ONNX models on CPU |
| FastAPI, uvicorn, pydantic, pydantic-settings | 0.162.0, 0.54.0, 2.14.1, 2.16.1 | MIT, BSD-3-Clause, MIT, MIT | web API |
| openai (Python SDK) | 3.37.0 | Apache-2.0 | client for the OpenAI-compatible Token Factory API |
| tavily-python | 0.8.5 | MIT | Tavily search and extract |
| httpx, numpy, pillow, pyyaml, python-multipart | 0.28.1, 2.5.4, 13.0.0, 6.0.3, 0.0.32 | BSD-3, BSD-3, MIT-CMU, MIT, Apache-2.0 | HTTP, arrays, images, config, uploads |
| React, react-router-dom | 19.3.1, 7.18.4 | MIT | web app |
| Vite, TypeScript, @vitejs/plugin-react, oxlint | 8.3, 6.0, 6.1, 1.88 | MIT, Apache-2.0, MIT, MIT | build tooling |
| Playwright, @axe-core/playwright | 1.64.1, 4.14.0 | Apache-2.0, MPL-2.0 | end-to-end and accessibility tests; demo-video recording |
| @fontsource: Atkinson Hyperlegible Next, Instrument Serif, IBM Plex Mono | 5.3.0 | OFL-1.1 | typefaces (also as TTF in `video/fonts/` for video cards) |
| ffmpeg (static build `mwader/static-ffmpeg:7.1.1` in the image) | 7.1.1 | GPL/LGPL build of FFmpeg, used as a separate executable | media processing |
| Kokoro-82M ONNX (`fastrtc/kokoro-onnx`) via kokoro-onnx | downloaded by `video/fetch_voices.sh` | Apache-2.0 (model), MIT (package) | voice for the demo video only |

### Media

| Media | Source | License | Use |
| --- | --- | --- | --- |
| *(3/4) Analysis: Explaining Fourier analysis with a machine* | engineerguy, Wikimedia Commons | CC BY 3.0 | example, evaluation, demo video |
| *A-level Physics Core Practical: Capacitor Discharge* | NUSTEM, Wikimedia Commons | CC BY 3.0 | example, evaluation |
| *How a Laser Works*, *CCD: the heart of a digital camera* | engineerguy, Wikimedia Commons | CC BY 3.0 | evaluation |
| *PubTalk 11/2011: USGS Science for a Changing Bay Area* | U.S. Geological Survey | Public domain | evaluation |
| *Yellowstone Volcano Observatory monthly update, November 2021* | U.S. Geological Survey, Wikimedia Commons | Public domain | held-out evaluation (metrics only) |
| *Vital Signs: Taking the Pulse of Our Planet* (Piers Sellers) | NASA Goddard, Wikimedia Commons | Public domain (one slide shows a meeting photo that may not be NASA's) | held-out evaluation (metrics only, not redistributed) |
| *Solving quadratic equations* | Mosborne01, Wikimedia Commons | CC BY-SA 3.0 | held-out evaluation (metrics only) |

## Submission record

No submission exists yet. At submission, record the exact source commit/tag, official submission URL, demo/video URLs, access checks and applicable freeze period. Do not put secrets or private judge passwords here.
