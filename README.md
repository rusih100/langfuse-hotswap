# langfuse-hotswap

*Hot-swap the LLM behind a LangChain chain from a Langfuse prompt.*

[![PyPI](https://img.shields.io/pypi/v/langfuse-hotswap)](https://pypi.org/project/langfuse-hotswap/)
[![Python](https://img.shields.io/pypi/pyversions/langfuse-hotswap)](https://pypi.org/project/langfuse-hotswap/)
[![Downloads](https://img.shields.io/pypi/dm/langfuse-hotswap)](https://pypistats.org/packages/langfuse-hotswap)
[![CI](https://github.com/rusih100/langfuse-hotswap/actions/workflows/ci.yml/badge.svg)](https://github.com/rusih100/langfuse-hotswap/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/rusih100/langfuse-hotswap/blob/main/LICENSE)

**English** | [Русский](README.ru.md)

**Documentation**: <https://rusih100.github.io/langfuse-hotswap>

<p align="center">
  <img src="docs/assets/demo.gif" width="800" alt="A service answering in a loop; the production label is moved to another version and the next answer comes from another model">
</p>

With [Langfuse](https://langfuse.com) prompt management the template lives outside the code. The
model does not: `gpt-5.5`, `temperature=0.2` sit next to the chain, and changing them is a deploy.

`langfuse-hotswap` moves the model into the prompt config. You build the chat models in the code
and get a regular [LangChain](https://github.com/langchain-ai/langchain) `Runnable` that fetches
the prompt on every call, picks the model and the parameters from its config and rebuilds when
the prompt changes. A prompt version is the template, the model and the parameters together:
labeled, rolled out and rolled back as one.

- **Any LangChain chat model.** `ChatOpenAI`, `ChatAnthropic`, `ChatOllama`, ... built in the code
  and selected from the config by name.
- **Explicit by default.** The config changes only the model fields the code allows, and nothing
  until it does. Credentials, endpoints and HTTP clients stay in the code.
- **Keeps serving.** A version that fails to build, or a Langfuse outage, leaves the last working
  chain in place.
- **A regular `Runnable`.** `invoke`, `stream`, `batch`, their async variants,
  `with_structured_output`, `bind_tools`, composition with other runnables.
- **Async without blocking.** Warm SDK cache is read on the event loop; HTTP goes to the executor.
- **Langfuse rendering rules**, or `f-string`, `mustache` and `jinja2` on request.
- **Traces link to the prompt version.**

## Installation

```shell
pip install langfuse-hotswap langchain-openai langchain-anthropic
```

## Example

Create a chat prompt `support-reply` in Langfuse, label it `production`, with the config:

```json
{"provider": "openai", "model": "gpt-5.5", "temperature": 0.2, "max_tokens": 800}
```

```python
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langfuse import get_client
from langfuse_hotswap import LangfuseChainFactory

factory = LangfuseChainFactory(
    get_client(),
    models={"openai": ChatOpenAI(model="gpt-5.5"), "anthropic": ChatAnthropic(model="claude-sonnet-5-5")},
    allowed_config_keys={"model", "temperature", "max_tokens"},
)
chain = factory.create("support-reply")

message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"})
print(message.content)
```

Now create a new version with `"provider": "anthropic", "model": "claude-sonnet-5-5"` and move
the `production` label to it. The next `invoke` runs on Anthropic. Move the label back and
it runs on OpenAI again. No restart, no deploy.


## Who controls what

Anyone who edits the prompt controls its config. The code decides how far that goes:

```python
factory = LangfuseChainFactory(
    get_client(),
    models={"openai": ChatOpenAI(api_key=..., timeout=30)},  # built here, credentials included
    allowed_config_keys={"model", "temperature", "max_tokens"},  # the only keys the config may change
)
```

`provider` selects one of the models. Without `allowed_config_keys` the config changes nothing
else; with `"any"` it changes everything, `base_url` and `api_key` included. See
[Security](https://rusih100.github.io/langfuse-hotswap/security/).

## Learn more

- [Concepts](https://rusih100.github.io/langfuse-hotswap/concepts/): the five parts in one page.
- [Models and config keys](https://rusih100.github.io/langfuse-hotswap/models/): what the prompt config may change and how.
- [Customizing the model](https://rusih100.github.io/langfuse-hotswap/customizing/): hooks, structured output, tools.
- [How it works](https://rusih100.github.io/langfuse-hotswap/how-it-works/): fetch, compare, rebuild, failures, the async path.
- [API reference](https://rusih100.github.io/langfuse-hotswap/api/).
- [`examples/`](examples/): one short script per feature.

Unofficial. Not affiliated with Langfuse or LangChain. MIT licensed.
