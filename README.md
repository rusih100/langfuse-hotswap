# langfuse-hotswap

[![PyPI](https://img.shields.io/pypi/v/langfuse-hotswap)](https://pypi.org/project/langfuse-hotswap/)
[![Python](https://img.shields.io/pypi/pyversions/langfuse-hotswap)](https://pypi.org/project/langfuse-hotswap/)
[![CI](https://github.com/rusih100/langfuse-hotswap/actions/workflows/ci.yml/badge.svg)](https://github.com/rusih100/langfuse-hotswap/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/rusih100/langfuse-hotswap/blob/main/LICENSE)

Hot-swap the LLM behind a [LangChain](https://github.com/langchain-ai/langchain) chain from a
[Langfuse](https://langfuse.com) prompt. The model and its parameters live in the prompt config,
so a prompt version is the template, the model and the parameters together. Change any of them in
Langfuse and the running service picks it up. Roll the prompt back and the model rolls back with it.

Unofficial. Not affiliated with Langfuse or LangChain.

## Purpose

With Langfuse prompt management the template is already managed outside the code: you edit it in
the UI, label a version `production` and the service fetches it. The model is not. `gpt-5.5`,
`temperature=0.2` and `max_tokens=800` sit in the code, next to the chain, and changing them means
a commit and a deploy. A prompt tuned for one model goes live with the model of the last deploy.

`langfuse-hotswap` moves the model into the prompt config:

```json
{"model": "gpt-5.5", "model_provider": "openai", "temperature": 0.2, "max_tokens": 800}
```

and gives you a LangChain `Runnable` that fetches the prompt on every call, builds
`prompt | model` from it and rebuilds when the prompt changes. The code decides what can be
changed from Langfuse, Langfuse decides the values.

### Key features

- **One prompt version, one model.** The template, the provider, the model name and the parameters
  are versioned, labeled and rolled back together.
- **Any provider `init_chat_model` knows.** OpenAI, Anthropic, Google, Mistral, Ollama and the rest
  of the LangChain integrations. Switching providers is a config edit.
- **A regular `Runnable`.** `invoke`, `ainvoke`, `stream`, `astream`, `batch`, `abatch`,
  `batch_as_completed`, `astream_events`, `with_fallbacks`, `with_retry` and composition with
  other runnables all work.
- **Safe by default.** Only known sampling parameters are taken from the config. Endpoints,
  credentials, headers, proxies, HTTP clients, timeouts and retries never are. The provider is
  always named explicitly, never guessed from the model name. Code settings override config
  settings.
- **Keeps serving.** If a new prompt version fails to build, or Langfuse cannot be reached at all,
  the last working chain keeps serving and the failure is logged.
- **Langfuse rendering rules.** Variables are rendered by the Langfuse SDK itself, so what you see
  in the playground is what the model gets. Placeholders are supported.
- **Traces link to the prompt.** The chain carries the prompt in its metadata, so traces from the
  Langfuse callback handler are linked to the prompt version.

## Quickstart

1. **Install the package** and the LangChain package of every provider you plan to use.

```shell
pip install langfuse-hotswap langchain-openai langchain-anthropic
```

2. **Create a prompt in Langfuse.** A chat prompt named `support-reply` with two messages:

```
system: You are a support assistant for {{product}}. Reply in {{language}}.
user:   {{question}}
```

and this config:

```json
{"model": "gpt-5.5", "model_provider": "openai", "temperature": 0.2, "max_tokens": 800}
```

Label the version `production`. The config keys are passed to the model constructor the same way
you would pass them to `init_chat_model`.

3. **Create the chain once**, at startup or at module level, and reuse it. It is a regular
   LangChain `Runnable`.

```python
from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

factory = LangfuseChainFactory(get_client())
chain = factory.create("support-reply")
```

4. **Call it.** The input is a dict of the prompt variables. The output is the model message.

```python
message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"})
print(message.content)
```

5. **Change the model in Langfuse.** Create a new version of `support-reply` with the config

```json
{"model": "claude-sonnet-5-5", "model_provider": "anthropic", "temperature": 0.2, "max_tokens": 800}
```

and move the `production` label to it. The next `chain.invoke(...)` runs on Anthropic. No
restart, no deploy. Move the label back and the next call runs on OpenAI again.

6. **(optional) Parse the output.** `with_structured_output` and `bind_tools` work like on a model
   and return a new chain.

```python
from pydantic import BaseModel


class Reply(BaseModel):
    text: str
    escalate_to_human: bool


typed_chain = factory.create("support-reply").with_structured_output(Reply)
reply = typed_chain.invoke({"product": "Acme Mail", "language": "English", "question": "I was charged twice."})
if reply.escalate_to_human:
    ...
```

<details>
<summary>Full example</summary>

```python
# env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY

from langfuse import get_client
from pydantic import BaseModel

from langfuse_hotswap import LangfuseChainFactory


class Reply(BaseModel):
    text: str
    escalate_to_human: bool


factory = LangfuseChainFactory(get_client())

chain = factory.create("support-reply")
typed_chain = chain.with_structured_output(Reply)

question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}

print(chain.invoke(question).content)
print(typed_chain.invoke(question).escalate_to_human)

for chunk in chain.stream(question):
    print(chunk.content, end="")
```

</details>

## How it works

Every call does three things:

1. **Fetch** the prompt through `client.get_prompt(...)`. The Langfuse SDK caches prompts and
   refreshes them in the background, so this is a dict lookup most of the time. Async methods
   fetch on the event loop once a chain is built from a prompt that came from Langfuse: the SDK
   then answers from its cache without blocking, even when the entry is stale. The first call,
   `cache_ttl_seconds=0`, a chain built from `fallback` and the calls after a failed fetch go to
   the executor instead, because there the SDK fetches over HTTP. A rebuild always runs in the
   executor. One case still blocks the loop for a single fetch: the SDK cache entry was dropped,
   because the prompt was deleted in Langfuse or a prompt was updated through the same client. An
   update drops the entries of every prompt whose name starts with the updated name, so updating
   `support` also drops `support-reply`.
2. **Compare** it with the prompt the current chain was built from. The SDK returns the same
   object until it refreshes the prompt, so most calls stop at an identity check. Otherwise prompts
   are compared by name, version, content and config. The version number alone would not do,
   because Langfuse gives a new prompt the number of a deleted latest version.
3. **Delegate** to the chain. If the prompt changed, the chain is rebuilt first: the model is
   created with `init_chat_model`, the hooks are applied, the template is built and
   `template | model` is cached. The rebuild runs under a lock, so concurrent callers build it
   once, and calls that arrive during the rebuild are served by the previous chain.

The runnable itself holds no model, only a chain for the current prompt. That is why it should be
created once and reused: a chain created inside a request handler rebuilds the model on every
request.

## Configuration

### Where the parameters come from

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

### Restricting the config

Anyone who can edit the prompt controls the model constructor arguments. Three guards:

1. **Allowlist.** By default only the keys in `DEFAULT_ALLOWED_CONFIG_KEYS` reach the model: the
   model, the provider and the common sampling parameters such as `temperature`, `max_tokens`,
   `top_p`, `seed`, `reasoning_effort` and `response_format`. Pass `allowed_config_keys` to narrow
   or widen the set, or `None` to pass every config key except the blocked ones. Values are not
   validated: `n`, `max_tokens` and the reasoning budget set the cost and the latency of a call,
   so narrow the set if the editors of the prompt should not control them.
   Provider-specific switches such as `safety_settings` are not in the default set; add them
   deliberately.
2. **Blocked keys.** Endpoints, regions, projects, credentials, TLS settings, headers, proxies,
   transports, timeouts, retries, HTTP clients, passthrough dicts such as `model_kwargs` and
   `extra_headers`, callbacks, caches, `configurable_fields` and `config_prefix` are never taken
   from the config, whatever the allowlist says. The full rule is `is_blocked_config_key`. It is
   built from the constructor arguments of the known provider packages and cannot be complete for
   every provider, so it is a second line of defense behind the allowlist.
   `allowed_config_keys=None` relies on it alone and is meant for prompts that only trusted people
   can edit: some models, `ChatOpenAI` among them, move unknown constructor arguments into the
   request body, so the editors of the prompt control fields such as `store`, `service_tier` and
   `metadata`.
3. **Labels.** Use a dedicated label for production and restrict who can edit it in Langfuse.

```python
factory = LangfuseChainFactory(
    langfuse,
    # Other config keys, such as "tools", do not reach the model. Hooks can still read them.
    allowed_config_keys={"model", "model_provider", "temperature", "max_tokens"},
)
```

### Selecting the prompt version

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

## Customizing the model

The model is built at run time, so it is customized through hooks that are stored on the chain and
applied on every rebuild. Every method returns a copy and the original is unchanged.

```python
chain = (
    factory.create("support-reply")
    .with_model(lambda model: model.with_retry(stop_after_attempt=3))
    .with_model(lambda model: model.bind(seed=42))
)
```

A hook with a parameter named `prompt` also receives the Langfuse prompt client, so it can read
the prompt config. It gets a copy, so it cannot affect the SDK cache.

Every copy returned by these methods has its own cache: it builds its own model, with its own
HTTP client, and rebuilds on its own when the prompt changes. Create the variants you need once
and reuse them, rather than deriving a new one per call.

```python
chain = factory.create("support-reply").with_model(
    lambda model, prompt: model.bind(tools=prompt.config.get("tools", []))
)
```

`with_structured_output(schema)` and `bind_tools(tools)` are shortcuts for the matching model
methods. Bind model arguments through a hook: `invoke` has no way to pass them, as in any
`prompt | model` chain.

## Error handling

All errors derive from `HotswapError`.

- `PromptFetchError`. The prompt could not be fetched and the SDK cache was empty, for example on
  a cold start during an outage, or after the prompt was deleted. With a previously built chain,
  the error is logged no more often than once a minute and that chain keeps serving. Without one,
  it is raised. Recovery is up to you, for example a local chain as a fallback:

  ```python
  from langfuse_hotswap import PromptFetchError

  chain = factory.create("support-reply").with_fallbacks([local_chain], exceptions_to_handle=(PromptFetchError,))
  ```

- `ChainBuildError`. The prompt was fetched but the chain could not be built: the config has no
  `model` or does not name the provider, the provider package is not installed, the model
  constructor rejected a parameter, a hook raised. With a previously built chain, the error is logged, that chain keeps serving and
  the build is retried no more often than once a minute. Without one, it is raised, and the calls
  of the next minute raise the same error without rebuilding, so a broken prompt on a cold start
  does not build a model per call.

With `return_exceptions=True`, `batch`, `abatch`, `batch_as_completed` and `abatch_as_completed`
return the error for every item instead of raising. Empty inputs return an empty result without
fetching the prompt.

## Templates

Messages are rendered with the Langfuse substitution rules, so the result matches the playground.
The renderer is a copy of the SDK `TemplateParser`, and a contract test checks that both produce
the same text.

- A variable is whatever stands between `{{` and the next `}}`, stripped. Values are inserted with
  `str()` without escaping and `None` becomes an empty string.
- Every variable is required. Unlike `prompt.compile()`, a missing variable is an error, not left
  as is. The check is the LangChain prompt template one, so the error is a `KeyError` that names
  the missing variables.
- Single braces and HTML are left as they are. There are no mustache sections: `{{#flag}}` is a
  variable named `#flag`.
- Placeholders are filled from the input variable of the same name, which must be a list of
  messages. Variables inside those messages are not rendered.
- A text prompt becomes one `human` message. Roles LangChain does not know, such as `developer`,
  are kept as `ChatMessage` with that role.
- Variables named `stop` and `self` are rejected by LangChain.

`get_input_schema` lists the prompt variables when Langfuse is reachable and falls back to a
permissive schema otherwise. The default run name is the prompt name; `with_config(run_name=...)`
overrides it.

## Limitations

- A model change in Langfuse changes production without a commit. Guard the production label.
- The output schema and the prompt variables are not versioned with the prompt.
- Until the SDK cache TTL expires, replicas may run different prompt versions.
- Build errors are logged with the exception text, which may include config values. The model
  constructor reports the values of the parameters it rejects, so a rejected credential passed
  through the factory kwargs would appear in the log.
- `copy` and `deepcopy` share the client and the hooks and start with an empty cache. Pickling is
  not supported.

## Requirements

Python 3.11+, `langchain>=1,<2`, `langchain-core>=1,<2`, `langfuse>=5,<6`.

## Development

```shell
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check
```

The library relies on behavior of the Langfuse SDK that its public API does not promise: the
fields of the prompt client, that a fresh cache entry is served as the same object, that a stale
one is served at once while the refresh runs in the background, and the rendering rules.
`tests/test_sdk_contract.py` pins each of these against a real client with a stubbed HTTP API, so
a change in the SDK fails the build instead of changing the behavior silently. CI runs the suite
on the lowest supported `langfuse` and on the locked version; a nightly workflow runs it on the
latest `langfuse` 5.x release.

The version comes from the git tag. To release, publish a GitHub Release with a `v*` tag, for
example `v0.2.0`, and generate its notes from the pull requests. The release workflow builds the
package and publishes it to PyPI. The history of versions is the
[releases page](https://github.com/rusih100/langfuse-hotswap/releases).

## License

MIT
