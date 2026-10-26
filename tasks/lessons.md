# Lessons

Rules learned from corrections during this project. Review at session start.

- **Git attribution:** never add `Co-Authored-By` trailers or AI-attribution lines to commits or PR descriptions.
- **Branching:** in this repo, commit and push directly to `master`; no feature branches, no PRs.
- **Flaky endpoints:** on an endpoint that fails intermittently, one failing request proves nothing about its
  parameters. Repeat each variant at least three times (and the passing control too) before blaming a parameter.
  Self-caught on Oct 26: a transient 500 was first reported as "json_schema fails with images", then a second one
  as "max_tokens overflows the context"; both requests succeeded when repeated.
- **Gate commits on exit status:** never chain `pytest | tail && git commit`; the pipe reports tail's status, so a
  failing suite still commits. Run the tests without a pipe (or with `set -o pipefail`) before committing.
  Self-caught on Oct 27 after pushing a failing assertion.
- **Held-out data:** never change the system because of what held-out results showed. If a held-out run was seen
  before a change, say so in the report.
