# Models and config keys

## Models

The chat models are built in the code and handed to the factory by name:

```python
import os

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

factory = LangfuseChainFactory(
    langfuse,
    models={
        "openai": ChatOpenAI(model="gpt-5.5", api_key=os.environ["OPENAI_API_KEY"], timeout=30),
        "anthropic": ChatAnthropic(model="claude-sonnet-5-5", api_key=os.environ["ANTHROPIC_API_KEY"]),
    },
    allowed_config_keys={"model", "temperature", "max_tokens"},
)
```

Any LangChain chat model works. Everything that is not JSON, such as credentials, endpoints, HTTP
clients and rate limiters, belongs in these constructors.

The prompt config selects a model with `provider`, a key of `models`:

```json
{"provider": "anthropic", "model": "claude-opus-5-5", "temperature": 0.2, "max_tokens": 800}
```

With one model `provider` may be omitted. With several it is required, and a name outside `models`
fails the build with `ChainBuildError`.

## Allowed config keys

Every config key other than `provider` and `template_format` is an override of a field of the
selected model. `allowed_config_keys` decides which overrides apply:

| Value | What the config can change |
|---|---|
| `None` (default) | Nothing. The config only selects the model. |
| A set of keys, `{"model", "temperature", "max_tokens"}` | Those fields. |
| `"any"` | Every field, `base_url` and `api_key` included. |

With the factory above, the config shown runs the chain on the Anthropic model with the model
name, the temperature and the token limit from the config; the credentials and the timeout stay as
built in the code. A key outside the set is ignored by the model but stays readable by hooks.
`template_format` in the set lets the config pick the renderer (see [Templates](templates.md)).

## How an override is applied

An override never changes the model passed to the factory. It creates a new object of the same
class from the fields of the selected model plus the config values, through the constructor, the
way `init_chat_model(configurable_fields=...)` does. So:

- The constructor validates the values. `"temperature": "hot"` fails the build with
  `ChainBuildError`, and the previous chain keeps serving.
- A config key may be a field name or its alias. `model` sets `model_name` on `ChatOpenAI`.
- Without overrides the chain runs on the model object itself.
- An HTTP client the model built at construction is carried over. `ChatOpenAI` keeps its client, so
  an override of `base_url` or `timeout` changes the field but not the requests; `ChatAnthropic`
  rebuilds its client from the new fields.

## Field names by provider

The keys are the constructor arguments of the model class, so they differ by provider. A key the
class does not know is ignored, or, as with `ChatOpenAI`, moved into `model_kwargs` with a warning.

| | `ChatOpenAI` | `ChatAnthropic` | `ChatGoogleGenerativeAI` | `ChatOllama` |
|---|---|---|---|---|
| Model name | `model` | `model` | `model` | `model` |
| Temperature | `temperature` | `temperature` | `temperature` | `temperature` |
| Token limit | `max_tokens` | `max_tokens` | `max_output_tokens` | `num_predict` |
