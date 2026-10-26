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

## Recording future work

For every imported component, record its upstream URL, immutable commit/version, license, purpose and changes. For every material project decision, record date, rationale and source. If a baseline project is reused, identify its pre-event commit and explain the event-period work separately.

### Third-party components and media

| Component | Version / source | License | Purpose |
| --- | --- | --- | --- |
| (added as dependencies and sample clips are introduced) | | | |

## Submission record

No submission exists yet. At submission, record the exact source commit/tag, official submission URL, demo/video URLs, access checks and applicable freeze period. Do not put secrets or private judge passwords here.
