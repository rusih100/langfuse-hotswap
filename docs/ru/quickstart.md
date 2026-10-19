# Быстрый старт

1. **Установите пакет** и интеграцию LangChain для каждого провайдера, который планируете
   использовать.

    ```shell
    pip install langfuse-hotswap langchain-openai langchain-anthropic
    ```

2. **Создайте промпт в Langfuse.** Чат-промпт с именем `support-reply` из двух сообщений:

    ```
    system: You are a support assistant for {{product}}. Reply in {{language}}.
    user:   {{question}}
    ```

    и со следующей конфигурацией:

    ```json
    {"model": "gpt-5.5", "model_provider": "openai", "temperature": 0.2, "max_tokens": 800}
    ```

    Присвойте версии метку `production`. Ключи конфигурации передаются в конструктор модели так
    же, как если бы вы передали их в `init_chat_model`.

3. **Создайте цепочку один раз** — при запуске приложения или на уровне модуля — и используйте
   её повторно. Это обычный `Runnable` LangChain.

    ```python
    from langfuse import get_client

    from langfuse_hotswap import LangfuseChainFactory

    factory = LangfuseChainFactory(get_client())
    chain = factory.create("support-reply")
    ```

4. **Вызовите её.** На вход подаётся словарь с переменными промпта, на выходе — сообщение модели.

    ```python
    message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"})
    print(message.content)
    ```

5. **Смените модель в Langfuse.** Создайте новую версию `support-reply` с конфигурацией

    ```json
    {"model": "claude-sonnet-5-5", "model_provider": "anthropic", "temperature": 0.2, "max_tokens": 800}
    ```

    и перенесите на неё метку `production`. Следующий вызов `chain.invoke(...)` уйдёт в
    Anthropic — без перезапуска и без деплоя. Верните метку обратно, и следующий вызов снова
    пойдёт в OpenAI.

6. **При необходимости разберите ответ.** `with_structured_output` и `bind_tools` работают так
   же, как у модели, и возвращают новую цепочку.

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

??? example "Полный пример"

    ```python
    # env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY

    from langfuse import get_client
    from pydantic import BaseModel

    from langfuse_hotswap import LangfuseChainFactory


    class Reply(BaseModel):
        text: str
        escalate_to_human: bool


    factory = LangfuseChainFactory(get_client())

    chain = factory.create("support-reply")
    typed_chain = chain.with_structured_output(Reply)

    question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}

    print(chain.invoke(question).content)
    print(typed_chain.invoke(question).escalate_to_human)

    for chunk in chain.stream(question):
        print(chunk.content, end="")
    ```

Другие сценарии — в каталоге
[`examples/`](https://github.com/rusih100/langfuse-hotswap/tree/main/examples): короткие
скрипты, по одному на каждую возможность.
