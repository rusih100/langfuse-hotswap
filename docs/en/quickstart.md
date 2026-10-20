# Quickstart

1. **Install the package** and the LangChain package of every provider you plan to use.

    ```shell
    pip install langfuse-hotswap langchain-openai langchain-anthropic
    ```

2. **Create a prompt in Langfuse.** A chat prompt named `support-reply` with two messages:

    ```
    system: You are a support assistant for {{product}}. Reply in {{language}}.
    user:   {{question}}
    ```

    and this config:

    ```json
    {"provider": "openai", "model": "gpt-5.5", "temperature": 0.2, "max_tokens": 800}
    ```

    Label the version `production`. `provider` names one of the models you give the factory; the
    other keys are constructor arguments of that model's class.

3. **Build the models and the chain once**, at startup or at module level, and reuse the chain. It
   is a regular LangChain `Runnable`.

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
    ```

4. **Call it.** The input is a dict of the prompt variables. The output is the model message.

    ```python
    message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"})
    print(message.content)
    ```

5. **Change the model in Langfuse.** Create a new version of `support-reply` with the config

    ```json
    {"provider": "anthropic", "model": "claude-sonnet-5-5", "temperature": 0.2, "max_tokens": 800}
    ```

    and move the `production` label to it. The next `chain.invoke(...)` runs on Anthropic. No
    restart, no deploy. Move the label back and the next call runs on OpenAI again.

6. **(optional) Parse the output.** `with_structured_output` and `bind_tools` work like on a model
   and return a new chain.

    ```python
    from pydantic import BaseModel


    class Reply(BaseModel):
        text: str
        escalate_to_human: bool


    typed_chain = factory.create("support-reply").with_structured_output(Reply)
    reply = typed_chain.invoke({"product": "Acme Mail", "language": "English", "question": "I was charged twice."})
    if reply.escalate_to_human:
        ...
    ```

??? example "Full example"

    ```python
    # env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY

    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI
    from langfuse import get_client
    from pydantic import BaseModel

    from langfuse_hotswap import LangfuseChainFactory


    class Reply(BaseModel):
        text: str
        escalate_to_human: bool


    factory = LangfuseChainFactory(
        get_client(),
        models={"openai": ChatOpenAI(model="gpt-5.5"), "anthropic": ChatAnthropic(model="claude-sonnet-5-5")},
        allowed_config_keys={"model", "temperature", "max_tokens"},
    )

    chain = factory.create("support-reply")
    typed_chain = chain.with_structured_output(Reply)

    question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}

    print(chain.invoke(question).content)
    print(typed_chain.invoke(question).escalate_to_human)

    for chunk in chain.stream(question):
        print(chunk.content, end="")
    ```

More in [`examples/`](https://github.com/rusih100/langfuse-hotswap/tree/main/examples): one short
script per feature.
