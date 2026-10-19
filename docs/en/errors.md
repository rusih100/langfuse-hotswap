# Error handling

All errors derive from `HotswapError`.

## `PromptFetchError`

The prompt could not be fetched and the SDK cache was empty, for example on a cold start during an
outage, or after the prompt was deleted. With a previously built chain, the error is logged no more
often than once a minute and that chain keeps serving. Without one, it is raised.

Recovery is up to you, for example a local chain as a fallback:

```python
from langfuse_hotswap import PromptFetchError

chain = factory.create("support-reply").with_fallbacks([local_chain], exceptions_to_handle=(PromptFetchError,))
```

or a fallback prompt, built with the model from the factory kwargs (see
[Configuration](configuration.md#selecting-the-prompt-version)).

## `ChainBuildError`

The prompt was fetched but the chain could not be built: the config has no `model` or does not
name the provider, the provider package is not installed, the model constructor rejected a
parameter, a hook raised.

With a previously built chain, the error is logged, that chain keeps serving and the build is
retried no more often than once a minute. Without one, it is raised, and the calls of the next
minute raise the same error without rebuilding, so a broken prompt on a cold start does not build
a model per call.

## Batches

With `return_exceptions=True`, `batch`, `abatch`, `batch_as_completed` and `abatch_as_completed`
return the error for every item instead of raising. Empty inputs return an empty result without
fetching the prompt.

## Schemas

`get_input_schema` lists the prompt variables when Langfuse is reachable and falls back to a
permissive schema otherwise. `get_output_schema` falls back to the default one.
