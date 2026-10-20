# langfuse-hotswap

A LangChain `Runnable` that picks its chat model and parameters from the Langfuse prompt config.
The models are built in the code; every call fetches the prompt through the Langfuse SDK cache and
delegates to `template | model` built for it; the chain is rebuilt when the prompt changes.

## Commands

```shell
uv sync                                   # install with the dev group
uv run pytest -q                          # tests
uv run ruff format . && uv run ruff check . && uv run ty check
uv run mkdocs build --strict                # after a docs change
```

Run all four before reporting a change as done. CI runs the same on Python 3.11–3.13.

## Layout

| Path | What lives there |
|---|---|
| `src/langfuse_hotswap/_factory.py` | `LangfuseChainFactory`: the models, the allowlist, `create`, the model for a prompt |
| `src/langfuse_hotswap/_prompts.py` | `PromptManager`: fetch, compare, rebuild under a lock, async fast path |
| `src/langfuse_hotswap/_runnable.py` | `LangfusePromptRunnable`: the `Runnable` interface, hooks, `template \| model` |
| `src/langfuse_hotswap/_template.py` | `LangfusePromptTemplate`: rendering with the SDK `TemplateParser` or a LangChain format |
| `src/langfuse_hotswap/_errors.py` | `HotswapError`, `PromptFetchError`, `ChainBuildError` |
| `tests/fakes.py`, `tests/conftest.py` | fake Langfuse client, fake chat model, `factory` and `builds` fixtures |
| `tests/test_<module>.py` | one test module per source module |
| `tests/test_sdk_contract.py` | the Langfuse SDK behavior the library relies on, run against a real client with a stubbed API |
| `examples/` | one short script per feature, flat, named by the feature; linted and type-checked, not tested |
| `docs/en`, `docs/ru`, `mkdocs.yml` | the documentation site (MkDocs Material + static-i18n, GitHub Pages); the README holds only the pitch and links there |
| `README.md`, `README.ru.md` | the English and the Russian pitch, kept in sync |
| `tools/render_demo_gif.py` | renders `docs/assets/demo.gif`, the README animation, with Pillow |
| `CHANGELOG.md` | Keep a Changelog format; every user-visible change gets a line under `Unreleased` |

The public API is what `src/langfuse_hotswap/__init__.py` imports. Modules are private (`_name.py`).

## Invariants

- The models and their credentials are built in the code; the config only selects one of them
  with `provider`, the key in `models`. Nothing is inferred from the model name.
- The config overrides only the model fields listed in `allowed_config_keys`: `None` (the
  default) means nothing, `"any"` means everything. The models passed to the factory are never
  mutated.
- A broken prompt never takes down a working chain: the previous chain keeps serving.
- The async path never blocks the event loop on HTTP when the SDK cache is cold.
- The only thing imported from `langfuse.model` at runtime is `TemplateParser`; nothing from
  `langfuse._utils`. Every assumption about the SDK (prompt fields, cache behavior, rendering)
  is pinned by a test in `tests/test_sdk_contract.py`.

Behavior changes go together with tests, the docs in both languages and a line in `CHANGELOG.md`.

## Conventions

Path-scoped rules in `.claude/rules/` load when matching files are touched: Python style, tests,
the factory, the runnable and the prompt manager, README and CI. The short version:

- Docstrings say what, not why, and are always multi-line.
- No `__all__`, no module-level constants for single literals.
- Never commit or create branches unless asked.
