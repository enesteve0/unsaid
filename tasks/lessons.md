# Lessons

Rules learned from corrections during this project. Review at session start.

- **Git attribution:** never add `Co-Authored-By` trailers or AI-attribution lines to commits or PR descriptions.
- **Branching:** in this repo, commit and push directly to `master`; no feature branches, no PRs.
- **Flaky endpoints:** on an endpoint that fails intermittently, one failing request proves nothing about its
  parameters. Repeat each variant at least three times (and the passing control too) before blaming a parameter.
  Self-caught on Oct 26: a transient 500 was first reported as "json_schema fails with images", then a second one
  as "max_tokens overflows the context"; both requests succeeded when repeated.
