# Nebius x NVIDIA Global AI Hackathon 2026: research

Checked: **2026-10-23**, rechecked **2026-10-26**. Every source below is an official organizer or sponsor page for the 2026 event. This report summarizes them and does not replace the official rules.

**Confirmed** means a cited source states it. **Unverified** means personal access or status was not tested. **Unresolved** means sources conflict or don't settle the point.

## Event and schedule

| Milestone | Pacific time | Istanbul time |
| --- | --- | --- |
| Submissions open | Aug 26, 2026, 09:00 PDT | 19:00 |
| Submission deadline | Oct 30, 2026, 10:00 PDT | 20:00 |
| Judging | Dec 1, 09:00 PST – Dec 15, 12:00 PST | ends Dec 15, 23:00 |
| Winners expected | around Jan 11, 2027 | — |

Demos must stay available until the judging period ends. [Rules](https://nebiusglobalaihackathon.devpost.com/rules), [schedule](https://nebiusglobalaihackathon.devpost.com/details/dates)

## Required technology (confirmed 2026-10-26)

The Official Rules define "Runs on Nebius Token Factory or Nebius AI Cloud" this way: "the project makes a runtime call to the Token Factory inference API, or is deployed/run using Nebius AI Cloud compute (Serverless Jobs, Serverless Endpoints, or DevPods)."

The FAQ adds that calling an NVIDIA model through Token Factory satisfies the requirement, and that the rest of the app need not be hosted on Nebius. Calling NVIDIA models through other providers such as Hugging Face or OpenRouter does not count. [Rules](https://nebiusglobalaihackathon.devpost.com/rules), [FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs)

### Track

This project is entered in **Best Apps and Agents**: "Build any app or agent someone would actually use... Power it with Nemotron models on Nebius through Token Factory." The track text recommends Nemotron 3 Ultra for heavy reasoning, Nano or Super for fast calls, and Serverless Endpoints or Jobs (optional).

## NVIDIA models on Token Factory (public catalog, read 2026-10-26)

Source: [public model catalog](https://tokenfactory.nebius.com/api/public/models_info). Prices are USD per 1M tokens.

| Model ID | Input | Context | Price in / out |
| --- | --- | --- | --- |
| `nvidia/Nemotron-3_5-Lightning` | text | 1M | 0.06 / 0.24 |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | text | 262k | 0.06 / 0.24 |
| `nvidia/nemotron-3-super-120b-a12b` | text | 262k | 0.30 / 0.90 |
| `nvidia/Nemotron-3.5-Super-VL` | text, image, video | 1M | 0.30 / 0.90 |
| `nvidia/Nemotron-3-Ultra-550b-a55b` | text | 1M | 1.00 / 3.00 |

Model IDs are case-sensitive. The API base URL is `https://api.tokenfactory.nebius.com/v1/`, and it is OpenAI-compatible.

## Deliverables

- **Repository:** public on GitHub, GitLab or Bitbucket, with an open-source license that shows in the About panel.
- **README:** setup and run instructions, and how NVIDIA models, Token Factory and other Nebius services are used.
- **Submission form:** a working demo URL, the chosen track, a project description, and feedback on the tools.
- **Video:** under three minutes, uploaded to YouTube and set to public.

[Rules](https://nebiusglobalaihackathon.devpost.com/rules)

## Judging

- **Stage one** is pass/fail: the project must reasonably fit its track's theme and reasonably use the required APIs/SDKs.
- **Stage two** scores four equal criteria from 1 to 5:
  - Technological Implementation (also the first tie-break);
  - Design;
  - Potential Impact;
  - Quality of the Idea.
- **Prize combinations:** a project wins either one Overall award, or one Track award plus one Bonus award.

[Rules](https://nebiusglobalaihackathon.devpost.com/rules)

## Licenses

| Model | License |
| --- | --- |
| Nemotron 3.5 Lightning, Nemotron 3.5 Super VL, Nemotron 3 Ultra | OpenMDW-1.1 |
| Nemotron 3 Nano, Nemotron 3 Super | NVIDIA Nemotron Open Model License |

The application's MIT license does not replace any model's license terms. [NVIDIA Nemotron license](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/)

## Maintenance

Recheck the official updates before submission. Record changes with their source URL and check date. Keep application claims tied to actual evidence, and update the [submission checklist](SUBMISSION.md) when the rules change.
