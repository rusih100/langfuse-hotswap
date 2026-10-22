# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-10-22

### Added

- `langfuse` 4.x support: the dependency is now `langfuse>=4,<6`. CI runs the tests on the lowest
  supported `langfuse` 4.0.0, and the nightly workflow on the latest 4.x and 5.x releases.

## [1.0.1] - 2026-10-21

The first stable release: the public API follows Semantic Versioning from here on.

### Added

- `hooks` on `LangfuseChainFactory`: model hooks applied to every chain from `create`, after the
  chain's own `with_model` hooks, so `with_structured_output` still gets the chat model. A single
  hook passed without a list raises `TypeError`.
- Python 3.14 support.

### Changed

- The package no longer depends on `langchain`; `langchain-core` is enough.

### Removed

- **Breaking.** `PromptManager` is no longer part of the public API.

## [0.2.0] - 2026-10-20

### Changed

- **Breaking.** `LangfuseChainFactory` takes the chat models built in the code: `models` maps a
  name to a `BaseChatModel`, and the prompt config selects one with `provider`. The models are
  never changed; an override creates a new object of the same class from the fields of the
  selected model and the config values, where a config key wins over the field it names or aliases.
- **Breaking.** `allowed_config_keys` is explicit: `None`, the default, lets the config override
  nothing; a set of keys overrides those fields; `"any"` passes every key. There is no default
  allowlist and no blocked keys.
- **Breaking.** The `langfuse` template format renders with the SDK `TemplateParser` instead of a
  copy of it; the contract test pins its rules.
- A version that fails to build is retried when the prompt changes instead of once a minute. A
  failed fetch is logged once per outage instead of once a minute.
- Concurrent first calls on a cold start fetch the prompt one at a time, so the SDK fetches once.
- The fetch, the comparison and the rebuild moved from the runnable into `PromptManager`.

### Added

- `template_format`: `langfuse` (default), `f-string`, `mustache` and `jinja2`, the last one with
  the `jinja2` extra. The prompt config key `template_format` selects it per prompt when
  `allowed_config_keys` names it; the factory argument is the default.
- `label` on the factory: the prompt label `create` uses when it gets neither a label nor a version.
- `create` passes every keyword argument other than `label` and `version` to `get_prompt`.
- `PromptManager` in the public API.

### Removed

- The factory kwargs (`model_kwargs`), `providers`, `DEFAULT_ALLOWED_CONFIG_KEYS`,
  `is_blocked_config_key` and the normalization of provider names.
- The `batch`, `abatch`, `batch_as_completed` and `abatch_as_completed` overrides; the inherited
  LangChain methods call `invoke` per input.
- `fallback` on `create`, which now rejects it. Use `with_fallbacks` with a local chain for a cold
  start without Langfuse.

## [0.1.1] - 2026-10-19

### Added

- Contract tests pin the Langfuse SDK behavior the library relies on: the prompt client fields,
  the cache serving a fresh entry as the same object and a stale one without blocking, and the
  rendering rules. CI runs the suite on the lowest supported `langfuse` and a nightly workflow on
  the latest 5.x release.
- Documentation site in English and Russian, published to GitHub Pages; the README is now a short
  pitch with an animated demo and links there. `README.ru.md` mirrors `README.md`.
- `examples/`: one short script per feature.
- `CHANGELOG.md`.

### Changed

- Prompts are compared by name, version, content and config in the library itself instead of the
  SDK `__eq__`; the template renderer is a copy of the SDK one, checked against it by a contract
  test. Nothing from the private SDK modules is imported at run time.
- The sdist contains the package, the tests and the changelog only.

## [0.1.0] - 2026-10-19

### Added

- `LangfuseChainFactory` and `LangfusePromptRunnable`: a LangChain `Runnable` that fetches a
  Langfuse prompt through the SDK cache, builds `template | model` from the prompt config with
  `init_chat_model` and rebuilds when the prompt changes.
- Config allowlist (`DEFAULT_ALLOWED_CONFIG_KEYS`, `allowed_config_keys`) and blocked keys
  (`is_blocked_config_key`): endpoints, credentials, headers, proxies, HTTP clients, timeouts and
  retries never come from the prompt config.
- `providers` on the factory limits the config to the providers the code has configured.
- The previous chain keeps serving when a new prompt version fails to build or Langfuse cannot be
  reached; failures are logged at most once a minute.
- Async methods fetch on the event loop when the SDK cache is warm and in the executor otherwise.
- `with_model`, `with_structured_output` and `bind_tools` return a copy with the hook applied on
  every rebuild.
- `LangfusePromptTemplate` renders prompts with the Langfuse substitution rules, placeholders
  included, and attaches the prompt to the trace metadata.

[Unreleased]: https://github.com/rusih100/langfuse-hotswap/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/rusih100/langfuse-hotswap/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/rusih100/langfuse-hotswap/compare/v0.2.0...v1.0.1
[0.2.0]: https://github.com/rusih100/langfuse-hotswap/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/rusih100/langfuse-hotswap/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/rusih100/langfuse-hotswap/releases/tag/v0.1.0
