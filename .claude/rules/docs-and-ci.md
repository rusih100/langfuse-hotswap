---
paths:
  - "README.md"
  - "CLAUDE.md"
  - ".claude/rules/**"
  - ".github/workflows/**"
---

# Documentation and CI

## README

- The README is the user documentation and holds the rationale that docstrings leave out.
- A change in behavior, defaults or the public API updates the README in the same change.
- Code samples in the README must run against the current API.

## CLAUDE.md and rules

- Written in English, the whole file.
- `CLAUDE.md` stays short: commands, layout, invariants. Detailed rules go to `.claude/rules/`
  with a `paths` front matter that limits them to the files they are about.

## GitHub Actions

- Pin every action to a full commit SHA with the version in a comment.
- Default `permissions: contents: read`; grant more per job only where needed.
- `actions/checkout` uses `persist-credentials: false`.
- The release builds and tests in a job without `id-token`; only the publish job gets
  `id-token: write`, and it runs no project code.
