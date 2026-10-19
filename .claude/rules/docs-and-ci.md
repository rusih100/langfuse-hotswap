---
paths:
  - "README.md"
  - "README.ru.md"
  - "CHANGELOG.md"
  - "docs/**"
  - "mkdocs.yml"
  - "examples/**"
  - "CLAUDE.md"
  - ".claude/rules/**"
  - ".github/workflows/**"
---

# Documentation and CI

## README and docs

- The README is the pitch, modeled on FastAPI and Dishka: tagline, badges, a link to the docs,
  one paragraph, a short feature list, install, one example, links. Under 120 lines. Everything
  else lives in `docs/`.
- `docs/` is the user documentation (MkDocs Material, published to GitHub Pages) and holds the
  rationale that docstrings leave out. A change in behavior, defaults or the public API updates
  the matching page in the same change. `uv run mkdocs build --strict` must pass.
- Code samples in the README and the docs must run against the current API.
- No diagrams in the README. The visual is `docs/assets/demo.gif`: a schematic UI animation
  (prompt versions, the production label moving, the trace list switching models) rendered by
  `tools/render_demo_gif.py` with Pillow, 1200×640, 12 s loop, under 1 MB. It is a drawing, not
  a screenshot of Langfuse: keep the look generic. Change the story in the script, re-render
  with `uv run python tools/render_demo_gif.py docs/assets/demo.gif`, and look at a
  few frames before shipping.

## Two languages

- English is the source: `README.md` and `docs/en/`. Russian mirrors it: `README.ru.md` and
  `docs/ru/`, same file names, same headings in the same order, identical code blocks.
- A change to an English page is applied to the Russian page in the same change, and the other
  way round. Never leave one language behind; `mkdocs build --strict` does not catch it.
- The Russian text is a translation of meaning, not of words: natural Russian, the same facts,
  the same code. Identifiers, config keys, class names, labels and error names stay in English.
- `nav` is translated once in `mkdocs.yml` (`nav_translations`); a new page is added there in
  both languages.

## Changelog and examples

- `CHANGELOG.md` follows Keep a Changelog. A user-visible change adds a line under `Unreleased`
  in the same change; a release renames the section to the version and the date.
- `examples/` is a flat list of short scripts named by the feature (`basic.py`, `tools.py`),
  as in anthropic-sdk-python and Dishka: no numbering, no README, a one-sentence module
  docstring, 15–30 lines, only the project dependencies. They run against real Langfuse and real
  providers, pass ruff and ty, are not tested and are not part of the sdist.

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
