# API reference

Everything below is importable from `langfuse_hotswap`.

## `LangfuseChainFactory`

```python
LangfuseChainFactory(
    client: Langfuse,
    models: Mapping[str, BaseChatModel],
    *,
    allowed_config_keys: Iterable[str] | Literal["any"] | None = None,
    label: str | None = None,
    template_format: Literal["langfuse", "f-string", "mustache", "jinja2"] = "langfuse",
    hooks: Iterable[Callable[..., Runnable]] | None = None,
)
```

| Argument | Meaning |
|---|---|
| `client` | The Langfuse client, usually `langfuse.get_client()`. |
| `models` | Name to chat model. The prompt config selects one with `provider`. Must not be empty. |
| `allowed_config_keys` | Config keys that may override model fields: `None` for none, a set, or `"any"`. A string other than `"any"` raises `TypeError`. |
| `label` | Prompt label `create` uses when given neither a label nor a version. |
| `template_format` | Renderer for prompts whose config does not set, or may not set, `template_format`. |
| `hooks` | Model hooks applied to every chain after its own `with_model` hooks. A single callable instead of a collection raises `TypeError`. See [Hooks for every chain](customizing.md#hooks-for-every-chain). |

### `create`

```python
factory.create(prompt_name: str, *, label: str | None = None, version: int | None = None, **get_prompt_kwargs) -> LangfusePromptRunnable[BaseMessage]
```

`label` and `version` together raise `ValueError`, so does an empty name. `fallback` raises
`TypeError`. Every other keyword argument goes to `client.get_prompt`.

## `LangfusePromptRunnable`

A `Runnable[dict[str, Any], Output]`. Input is a dict of prompt variables; `Output` is
`BaseMessage` unless a hook changes it.

| Method | Returns |
|---|---|
| `invoke`, `ainvoke`, `stream`, `astream`, `batch`, `abatch`, `astream_events`, `transform`, ... | The LangChain `Runnable` interface. `batch` and its variants are the inherited ones. |
| `with_model(hook)` | A copy whose model is replaced by `hook(model)` on every rebuild. A hook with a `prompt` parameter also receives a copy of the prompt client. |
| `with_structured_output(schema, **kwargs)` | A copy that parses the output with `model.with_structured_output`. |
| `bind_tools(tools, **kwargs)` | A copy with the tools bound by `model.bind_tools`. |
| `get_input_schema()`, `get_output_schema()` | The schema of the current chain, or a permissive one when Langfuse is unreachable. Fetches and builds the chain. |
| `copy.copy`, `copy.deepcopy` | A copy that shares the client and the hooks and starts with an empty cache. |

## `LangfusePromptTemplate`

A `BaseChatPromptTemplate` over the messages of a Langfuse prompt.
`LangfusePromptTemplate.from_prompt(prompt, template_format="langfuse")` builds it and attaches the
prompt as `metadata["langfuse_prompt"]`. See [Templates](templates.md).

## Errors

| Class | Raised when |
|---|---|
| `HotswapError` | Base class of the two below. |
| `PromptFetchError` | The prompt could not be fetched and there is no built chain. The SDK error is `__cause__`. |
| `ChainBuildError` | The chain could not be built and there is no previous chain. The original error is `__cause__`. |
