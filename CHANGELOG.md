# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/rusih100/langfuse-hotswap/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rusih100/langfuse-hotswap/releases/tag/v0.1.0
