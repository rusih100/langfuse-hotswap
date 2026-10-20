# Error handling

All errors derive from `HotswapError`.

## `PromptFetchError`

The prompt could not be fetched and the SDK cache was empty, for example on a cold start during an
outage, or after the prompt was deleted. With a previously built chain, that chain keeps serving
and the error is logged once, until a fetch succeeds again. Without one, it is raised.

Recovery is up to you, for example a local chain as a fallback:

```python
from langfuse_hotswap import PromptFetchError

chain = factory.create("support-reply").with_fallbacks([local_chain], exceptions_to_handle=(PromptFetchError,))
```

## `ChainBuildError`

The prompt was fetched but the chain could not be built: `provider` names a model the factory does
not have or is missing with several models, the model constructor rejected a config value, a hook
raised, the template format is not installed.

With a previously built chain, the error is logged once, that chain keeps serving and the build
is retried when the prompt changes. Without one, it is raised, and every call raises the same
error without rebuilding until the prompt changes, so a broken prompt on a cold start does not
build a model per call.

## Batches

`batch`, `abatch`, `batch_as_completed` and `abatch_as_completed` are the inherited LangChain
methods: they call `invoke` per input, and with `return_exceptions=True` return the error for every
item instead of raising.

## Schemas

`get_input_schema` lists the prompt variables when Langfuse is reachable and falls back to a
permissive schema otherwise. `get_output_schema` falls back to the default one.
