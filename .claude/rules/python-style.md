---
paths:
  - "**/*.py"
---

# Python style

## Docstrings

- Every docstring is multi-line: `"""` on its own line, the text, `"""` on its own line. No one-line form.
- In a function or method, one blank line separates the docstring from the code that follows.
- A docstring says what the object does or returns, in one or two sentences. Behavior that the
  caller must know (precedence, defaults, what is raised) may follow as a short second paragraph.
- No reasoning, consequences or motivation ("so that", "because", "this means"). The rationale
  belongs in the README or, when it is local and non-obvious, in a one-line code comment.
- Methods that implement the `Runnable` interface as is (`invoke`, `stream`, …) have no docstring.

## Layout of code

- Separate the logical steps of a function with one blank line: validation, computation, the
  result. Do not separate lines that form one step.
- A predicate used in a condition gets its own method or function when it has more than two
  clauses (see `_cache_is_warm`).
- Group a module as: module docstring, imports, type variables, logger, private helper types,
  public classes, module-level helper functions.
- Pure logic that does not need the runnable state belongs in its own module (see `_config.py`).

## Code

- No `__all__`. The public API is whatever `__init__.py` imports.
- Do not extract a single string or number into a module-level constant; inline it.
- Prefer `NamedTuple` with named fields over bare tuples that are indexed.
- `from __future__ import annotations` in every module; imports used only in annotations go under
  `if TYPE_CHECKING:`.
- Line length is 120, ruff formats and lints, `ty` type-checks. Fix the code, not the config.
