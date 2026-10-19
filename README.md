# langfuse-hotswap

*Hot-swap the LLM behind a LangChain chain from a Langfuse prompt.*

[![PyPI](https://img.shields.io/pypi/v/langfuse-hotswap)](https://pypi.org/project/langfuse-hotswap/)
[![Python](https://img.shields.io/pypi/pyversions/langfuse-hotswap)](https://pypi.org/project/langfuse-hotswap/)
[![CI](https://github.com/rusih100/langfuse-hotswap/actions/workflows/ci.yml/badge.svg)](https://github.com/rusih100/langfuse-hotswap/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/rusih100/langfuse-hotswap/blob/main/LICENSE)

**English** | [Русский](README.ru.md)

**Documentation**: <https://rusih100.github.io/langfuse-hotswap>

<p align="center">
  <img src="docs/assets/demo.gif" width="800" alt="A service answering in a loop; the production label is moved to another version and the next answer comes from another model">
</p>

With [Langfuse](https://langfuse.com) prompt management the template lives outside the code. The
model does not: `gpt-5.5`, `temperature=0.2` sit next to the chain, and changing them is a deploy.

`langfuse-hotswap` moves the model into the prompt config. You get a regular
[LangChain](https://github.com/langchain-ai/langchain) `Runnable` that fetches the prompt on every
call, builds `template | model` from its config and rebuilds when the prompt changes. A prompt
version is the template, the model and the parameters together: labeled, rolled out and rolled
back as one.

- **Any provider** `init_chat_model` knows: OpenAI, Anthropic, Google, Mistral, Ollama, ...
- **Safe by default.** Only sampling parameters come from the config. Endpoints, credentials,
  headers and HTTP clients never do. Code settings override config settings.
- **Keeps serving.** A version that fails to build, or a Langfuse outage, leaves the last working
  chain in place.
- **A regular `Runnable`.** `invoke`, `stream`, `batch`, their async variants,
  `with_structured_output`, `bind_tools`, composition with other runnables.
- **Async without blocking.** Warm SDK cache is read on the event loop; HTTP goes to the executor.
- **Traces link to the prompt version.**

## Installation

```shell
pip install langfuse-hotswap langchain-openai
```

## Example

Create a chat prompt `support-reply` in Langfuse, label it `production`, with the config:

```json
{"model": "gpt-5.5", "model_provider": "openai", "temperature": 0.2, "max_tokens": 800}
```

```python
from langfuse import get_client
from langfuse_hotswap import LangfuseChainFactory

factory = LangfuseChainFactory(get_client())
chain = factory.create("support-reply")

message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"})
print(message.content)
```

Now create a new version with `"model": "claude-sonnet-5-5", "model_provider": "anthropic"` and
move the `production` label to it. The next `invoke` runs on Anthropic. Move the label back and
it runs on OpenAI again. No restart, no deploy.


## Who controls what

Anyone who edits the prompt controls its config. The code decides how far that goes:

```python
factory = LangfuseChainFactory(
    get_client(),
    timeout=30,  # overrides the config
    providers={"openai": {...}, "anthropic": {...}},  # the config may pick only these
    allowed_config_keys={"model", "model_provider", "temperature", "max_tokens"},
)
```

`base_url`, `api_key`, headers, proxies and the like never reach the model, whatever the allowlist
says. The provider is never inferred from the model name. See
[Security](https://rusih100.github.io/langfuse-hotswap/security/).

## Learn more

- [How it works](https://rusih100.github.io/langfuse-hotswap/how-it-works/): fetch, compare, rebuild, the async path.
- [Configuration](https://rusih100.github.io/langfuse-hotswap/configuration/): where parameters come from, labels and versions.
- [Customizing the model](https://rusih100.github.io/langfuse-hotswap/customizing/): hooks, structured output, tools.
- [Error handling](https://rusih100.github.io/langfuse-hotswap/errors/) and [templates](https://rusih100.github.io/langfuse-hotswap/templates/).
- [`examples/`](examples/): one short script per feature.

Unofficial. Not affiliated with Langfuse or LangChain. MIT licensed.
