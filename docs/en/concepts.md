# Concepts

Five things make up the library. The guide has a page for each of the first three; the last two
are described in [How it works](how-it-works.md).

**Factory.** `LangfuseChainFactory` holds what the chains share: the Langfuse client, the chat
models built in the code, the allowlist of config keys and the defaults for the prompt label and
the template format. Create one at startup and keep it.

**Models.** Regular LangChain chat models, `ChatOpenAI(...)`, `ChatAnthropic(...)` or any other,
built in the code with their credentials, endpoints and HTTP clients and handed to the factory
under a name. The prompt config refers to a model by that name and may override some of its fields.
See [Models and config keys](models.md).

**Prompt config.** The JSON config of a Langfuse prompt version. Two keys select: `provider` picks
a model by name, `template_format` picks a renderer. Every other key is an override of a field of
the selected model and reaches it only when `allowed_config_keys` permits. Hooks can read the whole
config, allowed or not. See [Models and config keys](models.md) and [Security](security.md).

**Chain.** `factory.create(name)` returns a `LangfusePromptRunnable`: a regular LangChain
`Runnable` whose input is a dict of prompt variables and whose output is the model message. Inside
it is `template | model`, built from the current prompt version and rebuilt when the version
changes. `with_model`, `with_structured_output` and `bind_tools` customize the model on every
rebuild. See [Customizing the model](customizing.md).

**Prompt manager.** An internal object, one per chain, fetches the prompt through the SDK cache,
compares it with the one the chain was built from and rebuilds under a lock. It keeps the last
working chain through broken versions and Langfuse outages. See [How it works](how-it-works.md).
