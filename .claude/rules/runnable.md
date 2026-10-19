---
paths:
  - "src/langfuse_hotswap/_runnable.py"
---

# The runnable

- Every `Runnable` method resolves the chain once (`_prepare` or `_aprepare`) and delegates to it.
  A batch method fetches the prompt once for all inputs.
- `_built` and `_failed` are replaced as whole `NamedTuple`s, never mutated, so readers outside the
  lock see a consistent pair.
- Rebuilds run under `_lock`. Without a built chain callers wait for the build; with one, a call
  that finds the lock taken is served by the previous chain.
- A failed build is cached for a minute in `_failed`; a failed fetch is logged at most once a
  minute. Both keep serving the previous chain.
- Async: fetch on the event loop only when `_cache_is_warm()` is true; otherwise, and for every
  rebuild, go through `run_in_executor`. Never call a blocking fetch or build directly in an
  `async def`.
- Hooks and the template metadata get a deep copy of the prompt; the original is kept only for
  comparison. Compare prompts by identity first, then by content.
- Errors leaving the runnable are `PromptFetchError` or `ChainBuildError` with the original as
  `__cause__`.
