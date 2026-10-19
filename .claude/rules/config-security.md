---
paths:
  - "src/langfuse_hotswap/_config.py"
  - "src/langfuse_hotswap/_factory.py"
---

# Model parameters and their security

Anyone who can edit a prompt in Langfuse controls its config. These rules keep that from
becoming control over endpoints, credentials or cost.

- Precedence is fixed: prompt config < factory kwargs < provider kwargs. Never let the config
  override something set in code.
- The provider comes only from an explicit `model_provider`. Do not infer it from the model name
  and do not parse a `provider:model` prefix. The model name is passed as is.
- With `providers` set, the config may select only one of those providers.
- `DEFAULT_ALLOWED_CONFIG_KEYS` holds sampling parameters only. Infrastructure (timeouts,
  retries, endpoints, clients, credentials) never goes there.
- `is_blocked_config_key` is the second line of defense and applies even with
  `allowed_config_keys=None`. When adding a provider-specific infrastructure argument, block it by
  exact name or by a prefix/suffix rule, and add it to the blocked-keys test in `test_config.py`.
- `build_model_params` stays a pure function: no I/O, no logging, no model construction.
