# langfuse-hotswap

*Hot-swap the LLM behind a LangChain chain from a Langfuse prompt.*

With [Langfuse](https://langfuse.com) prompt management the template lives outside the code: you
edit it in the UI, label a version `production` and the service fetches it. The model does not.
`gpt-5.5`, `temperature=0.2` and `max_tokens=800` sit in the code next to the chain, and changing
them is a commit and a deploy. A prompt tuned for one model goes live with the model of the last
deploy.

`langfuse-hotswap` moves the model into the prompt config:

```json
{"model": "gpt-5.5", "model_provider": "openai", "temperature": 0.2, "max_tokens": 800}
```

and gives you a [LangChain](https://github.com/langchain-ai/langchain) `Runnable` that fetches the
prompt on every call, builds `template | model` from it and rebuilds when the prompt changes. The
code decides what can be changed from Langfuse, Langfuse decides the values.

## Features

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
  settings. See [Security](security.md).
- **Keeps serving.** If a new prompt version fails to build, or Langfuse cannot be reached at all,
  the last working chain keeps serving and the failure is logged.
- **Langfuse rendering rules.** Variables are rendered with the Langfuse substitution rules, checked
  against the SDK by a contract test, so what you see in the playground is what the model gets.
  Placeholders are supported.
- **Traces link to the prompt.** The chain carries the prompt in its metadata, so traces from the
  Langfuse callback handler are linked to the prompt version.

## Compared with the SDK alone

The Langfuse SDK already gives you `get_prompt()` and `prompt.get_langchain_prompt()`. Reading
`prompt.config["model"]` and calling `init_chat_model` with it is a few lines. The rest is what
the few lines leave out:

| | `get_prompt` + `init_chat_model` by hand | `langfuse-hotswap` |
|---|---|---|
| Model follows the prompt version | You write it | Yes |
| Rebuild only when the prompt changes | You cache the model and compare prompts | Identity check, then name, version, content and config |
| Concurrent calls during a rebuild | You take a lock | Built once; callers are served by the previous chain |
| New version fails to build | Every call fails | Previous chain keeps serving, failure logged once a minute, retried once a minute |
| Langfuse unreachable, cache empty | `get_prompt` raises | `PromptFetchError`; with a built chain it keeps serving |
| Prompt editor sets `base_url` or `api_key` | Reaches the model constructor | Never reaches it: allowlist plus blocked keys |
| Prompt editor switches provider | Whatever is installed | Only providers the code configured, named explicitly |
| `ainvoke` on a cold SDK cache | Blocks the event loop on HTTP | Runs in the executor; a warm cache is served on the loop |
| Rendering | `get_langchain_prompt()` rewrites `{{x}}` to `{x}` and escapes braces | Langfuse rules, placeholders, missing variable is an error |
| Structured output, tools, retries | Rebuilt with the model | `with_structured_output`, `bind_tools`, `with_model` hooks applied on every rebuild |
| Trace linked to the prompt version | You pass the prompt in metadata | Attached to every run |

## When not to use it

- **One prompt, one model, no plans to change it from the UI.** `get_prompt()` and
  `init_chat_model()` are enough.
- **The model must never change without a code review.** The whole point is that a label move
  changes production. Keep the model in the code and use Langfuse for the template only.
- **The model must vary per request** (per tenant, per user tier). The chain follows the prompt,
  not the request. Create one chain per prompt and route between them.
- **No LangChain.** The library is a LangChain `Runnable` and builds models with
  `init_chat_model`.
- **Prompts that untrusted people can edit.** The guards keep endpoints and credentials out of
  reach, but whoever edits the prompt still controls the model, the token budget and the cost.
  Restrict the `production` label in Langfuse first.

## Requirements

Python 3.11+, `langchain>=1,<2`, `langchain-core>=1,<2`, `langfuse>=5,<6`. The package ships
`py.typed`.

Unofficial. Not affiliated with Langfuse or LangChain.
