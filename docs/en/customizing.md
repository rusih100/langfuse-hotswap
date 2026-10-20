# Customizing the model

The model is built at run time, so it is customized through hooks that are stored on the chain and
applied on every rebuild. Every method returns a copy and the original is unchanged.

```python
chain = (
    factory.create("support-reply")
    .with_model(lambda model: model.with_retry(stop_after_attempt=3))
    .with_model(lambda model: model.bind(seed=42))
)
```

A hook with a parameter named `prompt` also receives the Langfuse prompt client, so it can read
the whole prompt config, allowed keys or not. It gets a copy, so it cannot affect the SDK cache.

```python
chain = factory.create("support-reply").with_model(
    lambda model, prompt: model.bind(tools=prompt.config.get("tools", []))
)
```

`with_structured_output(schema)` and `bind_tools(tools)` are shortcuts for the matching model
methods:

```python
typed_chain = factory.create("support-reply").with_structured_output(Reply)
tool_chain = factory.create("support-reply").bind_tools([open_ticket])
```

Bind model arguments through a hook: `invoke` has no way to pass them, as in any `prompt | model`
chain.

Every copy returned by these methods has its own cache: it builds its own chain and rebuilds on
its own when the prompt changes. Create the variants you need once
and reuse them, rather than deriving a new one per call.

## Run name and tracing

The default run name is the prompt name; `with_config(run_name=...)` overrides it. The chain
carries the prompt in its run metadata, so the Langfuse callback handler links every generation to
the prompt version:

```python
from langfuse.langchain import CallbackHandler

message = chain.invoke(question, config={"callbacks": [CallbackHandler()]})
```
