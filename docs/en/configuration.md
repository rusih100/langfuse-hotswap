# Configuration

## Where the parameters come from

| Source | What goes there | Examples |
|---|---|---|
| Langfuse prompt config | Everything tuned together with the prompt | `model`, `model_provider`, `temperature`, `max_tokens`, `reasoning_effort` |
| Factory kwargs | Infrastructure and anything that is not JSON | HTTP clients, rate limiters, credentials, endpoints, timeouts, retries |

The merged parameters are passed to `init_chat_model`. Precedence, lowest first: prompt config,
factory kwargs, provider kwargs. The code always wins, so a prompt edit cannot change what the code
has set.

```python
factory = LangfuseChainFactory(
    langfuse,
    # Passed to every provider, overrides the prompt config.
    timeout=30,
    max_retries=2,
    # Passed only when the prompt config selects that provider.
    providers={
        "openai": {"base_url": "http://localhost:11434/v1", "api_key": "ollama"},
        "google_genai": {"vertexai": True, "project": "my-gcp-project"},
    },
)
```

- Factory kwargs go to every provider. A provider whose constructor rejects one of them fails to
  build, so credentials, endpoints and other provider-specific kwargs belong under `providers`.
- The config must name the provider through `model_provider`. It is never inferred from the
  model name: `{"model": "claude-sonnet-5-5"}` alone raises `ChainBuildError`, so renaming the
  model cannot silently move the requests, and the credentials with them, to another provider.
  The `provider:model` syntax of `init_chat_model` is not supported: the model name is passed as
  is, so `ft:gpt-4o-mini:org::id` is a model name. Provider names are normalized like
  `init_chat_model` does: `google-genai` and `google_genai` are the same.
- Without `providers`, the config may select any provider package that is installed, and that
  provider gets the factory kwargs and the credentials from the environment. Set `providers` to
  limit the config to the providers the code has configured, or pin one provider for every prompt
  with `model_provider` in the factory kwargs.
- With `providers`, the config may select only one of those providers.
- Without `model` in the merged parameters the chain raises `ChainBuildError`.

## Selecting the prompt version

`create` takes `label` or `version` and the `get_prompt` options `cache_ttl_seconds`, `fallback`,
`max_retries` and `fetch_timeout_seconds`.

```python
chain = factory.create("support-reply", label="staging", cache_ttl_seconds=30)
pinned = factory.create("support-reply", version=12)
```

`fallback` is used when the fetch fails and the SDK cache is empty. Its config is empty, so it
needs `model` and `model_provider` in the factory kwargs to be useful. The SDK does not
deduplicate concurrent requests on an empty cache, so warm the chain up on startup if many calls
arrive at once, for example with `chain.get_input_schema()`, which fetches the prompt and builds
the chain.
