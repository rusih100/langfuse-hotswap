---
paths:
  - "src/langfuse_hotswap/_runnable.py"
  - "src/langfuse_hotswap/_prompts.py"
---

# The runnable and the prompt manager

- `PromptManager` owns the fetch, the comparison and the rebuild of one prompt. The runnable owns
  the `Runnable` interface, the hooks and the `template | model` build. Keep that split: no model
  or template code in `_prompts.py`, no lock or cache in `_runnable.py`.
- Every `Runnable` method resolves the chain once (`_prepare` or `_aprepare`) and delegates to it.
  `batch` and friends are inherited from LangChain and not overridden.
- `_built` and `_failed` are replaced as whole `NamedTuple`s, never mutated, so readers outside the
  lock see a consistent pair.
- Rebuilds run under `_lock`, and so does the whole fetch-and-build on a cold start, so concurrent
  first calls fetch once. Without a built value callers wait for the build; with one, a call that
  finds the lock taken is served by the previous value. The lock is an `RLock` for that reason.
- A failed build is cached in `_failed` until the prompt changes; a failed fetch is logged once per
  outage, tracked by `_fetch_failed`. Both keep serving the previous value. There are no time windows.
- `_current` returns the `_Built` record, not the value, so a built value of `None` is a cache hit.
- Async: fetch on the event loop only when `_cache_is_warm()` is true; otherwise, and for every
  rebuild, go through `run_in_executor`. Never call a blocking fetch or build directly in an
  `async def`.
- Hooks and the template metadata get a deep copy of the prompt; the original is kept only for
  comparison. Compare prompts by identity first, then by content.
- Errors leaving the runnable are `PromptFetchError` or `ChainBuildError` with the original as
  `__cause__`.
