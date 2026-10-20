---
paths:
  - "src/langfuse_hotswap/_factory.py"
---

# Models and the config allowlist

Anyone who can edit a prompt in Langfuse controls its config. These rules keep that from
becoming control over endpoints, credentials or cost.

- The chat models are built in the code and passed to the factory as `models`, a mapping from a
  name to a `BaseChatModel`. The config selects one with `provider`, the key of that mapping.
  Nothing else selects a model: no inference from the model name, no `provider:model` prefix.
- `provider` and `template_format` are selectors read by the factory, never passed to the model
  constructor, not even with `"any"`. `provider` is always honored; `template_format` from the config
  only when the allowlist names it.
- `create` rejects `fallback`: a fallback prompt has an empty config and cannot select a model.
- `allowed_config_keys` is the only filter and it is explicit: `None` (the default) lets the
  config override nothing, a set of keys overrides those fields, `"any"` passes every key. There
  is no default allowlist and no blocked-keys list; do not add either.
- An override never mutates the model passed to the factory. It builds a new object of the same
  class from the fields of the selected model (`__dict__` filtered to `model_fields`) and the
  config values, the way `RunnableConfigurableFields` in langchain_core does, so the constructor
  validates the values and aliases such as `model` work. Without overrides the chain runs on the
  model object itself.
- `_model_for` stays pure: no I/O, no logging. Any failure in it is wrapped into `ChainBuildError`
  by the runnable.
- A security rule (default `None`, the allowlist, `provider` selection) gets a test in
  `tests/test_factory.py` that tries to break it.
