# Contribution workflow

Start with [research](docs/RESEARCH.md), [the submission checklist](docs/SUBMISSION.md) and [agent instructions](AGENTS.md).

Per the owner's instruction of 2026-10-26, work happens directly on `master`. There are no feature branches or pull requests. Keep commits small and focused, use conventional prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `test:`), and never add co-author or AI-attribution lines.

For documentation, review internal links, factual sources, dates and `git diff --check`. For application changes, run the backend tests (`uv run pytest` in `backend/`) and the web build, then check the demonstrated user journey. CI runs on every push.

Record reused work, licenses and significant decisions in [provenance](docs/PROVENANCE.md). Keep secrets outside Git, respect publication instructions, and observe the event-specific submission freeze.
