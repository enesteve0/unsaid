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
- **Fixes need their own review:** a batch of security and queue fixes looked complete, and its tests passed. A fresh
  review of that diff still found 12 problems: a cleanup glob (`s*.mp4`) that deleted the uploaded `source.mp4`, a
  proxy header trusted on every host, a service-wide pause that any visitor could trigger with broken uploads, and
  a reserve that concurrent requests could all pass. After fixing review findings, have the diff reviewed again,
  and write a test for each fix that fails on the old code. Self-caught on Oct 29.
- **Claims follow the deployment:** text about where the app runs (footer, Devpost, video narration) is derived
  from what the deployed app reports, never written ahead of it.
- **Never reset a file to undo a script's output when it also holds unsaved edits:** `git checkout README.md` to drop
  a generated table also dropped an hour's uncommitted README changes. Commit hand edits before running generators
  that write to the same file, or restore from a copy taken just before. Self-caught on Oct 29.
- **Open forms from the organizer's link:** a typed or shortened URL can drop parameters the form needs. The bare
  nebius.com/promo-code page took the owner's details and then failed with "no event name found"; the Devpost link
  carries the event and activation code. Before sending the owner to a form, open it from the official link and
  compare its query string with the bare URL. Found on Oct 30, after the owner's first submission failed.
