# langfuse-hotswap

*Hot-swap the LLM behind a LangChain chain from a Langfuse prompt.*

With [Langfuse](https://langfuse.com) prompt management the template lives outside the code: you
edit it in the UI, label a version `production` and the service fetches it. The model does not.
`gpt-5.5`, `temperature=0.2` and `max_tokens=800` sit in the code next to the chain, and changing
them is a commit and a deploy. A prompt tuned for one model goes live with the model of the last
deploy.

`langfuse-hotswap` moves the model into the prompt config:

```json
{"provider": "openai", "model": "gpt-5.5", "temperature": 0.2, "max_tokens": 800}
```

and gives you a [LangChain](https://github.com/langchain-ai/langchain) `Runnable` that fetches the
prompt on every call, builds `template | model` from it and rebuilds when the prompt changes. The
code builds the models and decides which of their fields Langfuse may change, Langfuse decides the
values.

## Features

- **One prompt version, one model.** The template, the provider, the model name and the parameters
  are versioned, labeled and rolled back together.
- **Any LangChain chat model.** Build `ChatOpenAI`, `ChatAnthropic`, `ChatGoogleGenerativeAI`,
  `ChatOllama` or any other in the code and hand them to the factory by name. Switching between
  them is a config edit.
- **A regular `Runnable`.** `invoke`, `ainvoke`, `stream`, `astream`, `batch`, `abatch`,
  `astream_events`, `with_fallbacks`, `with_retry` and composition with other runnables all work.
- **Explicit by default.** The config changes only the model fields the code lists in
  `allowed_config_keys`, and nothing until it does. Credentials, endpoints and HTTP clients live in
  the model objects the code built.
- **Keeps serving.** If a new prompt version fails to build, or Langfuse cannot be reached at all,
  the last working chain keeps serving and the failure is logged.
- **Langfuse rendering rules, or yours.** Variables are rendered by the SDK `TemplateParser`, so
  what you see in the playground is what the model gets. Placeholders are supported. `f-string`,
  `mustache` and `jinja2` are a `create` argument away.
- **Traces link to the prompt.** The chain carries the prompt in its metadata, so traces from the
  Langfuse callback handler are linked to the prompt version.

## When not to use it

- **One prompt, one model, no plans to change it from the UI.** `get_prompt()` and
  `init_chat_model()` are enough.
- **The model must never change without a code review.** The whole point is that a label move
  changes production. Keep the model in the code and use Langfuse for the template only.
- **The model must vary per request** (per tenant, per user tier). The chain follows the prompt,
  not the request. Create one chain per prompt and route between them.
- **No LangChain.** The library is a LangChain `Runnable` over LangChain chat models.
- **Prompts that untrusted people can edit.** By default they can only switch between the models
  the code built, but every allowed key is a parameter they control, the token budget and the cost
  among them. Restrict the `production` label in Langfuse first.

## Requirements

Python 3.11+, `langchain-core>=1,<2`, `langfuse>=5,<6`, plus the LangChain
package of every provider you use. The `jinja2` template format needs the `jinja2` extra. The
package ships `py.typed`.

Unofficial. Not affiliated with Langfuse or LangChain.

## Where next

[Quickstart](quickstart.md) gets a chain running in six steps. [Concepts](concepts.md) names the
parts; the guide has a page per part. [How it works](how-it-works.md) explains the mechanism and
compares the library with the SDK alone.
