# Prompt versions

`create` takes `label` or `version`. Without both, the factory `label` applies, and without that
one the `production` label.

```python
staging = LangfuseChainFactory(langfuse, models=models, label="staging")

chain = staging.create("support-reply")  # label "staging"
live = staging.create("support-reply", label="production")
pinned = staging.create("support-reply", version=12)  # the factory label does not apply
```

Every other keyword argument of `create`, such as `cache_ttl_seconds`, `max_retries` or
`fetch_timeout_seconds`, is passed to `client.get_prompt` as it is:

```python
chain = factory.create("support-reply", cache_ttl_seconds=30)
```

## Cache and replicas

The SDK caches each prompt and refreshes it in the background after `cache_ttl_seconds`, 60 by
default. A label move reaches a running service within that time, and until it does, replicas may
run different versions. `cache_ttl_seconds=0` fetches on every call.

## Warming up

The first call of a chain fetches the prompt over HTTP and builds `template | model`. Concurrent
first calls fetch once. To take that off the first request, warm the chain up at startup:

```python
chain.get_input_schema()  # fetches the prompt and builds the chain
```

A cold start while Langfuse is unreachable raises `PromptFetchError`; see
[Error handling](errors.md#promptfetcherror) for a local fallback.
