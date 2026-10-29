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
