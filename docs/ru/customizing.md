# Настройка модели

Модель создаётся во время работы приложения, поэтому настраивается через хуки. Хуки хранятся в
цепочке и применяются при каждой пересборке. Каждый метод возвращает копию цепочки; исходная
остаётся без изменений.

```python
chain = (
    factory.create("support-reply")
    .with_model(lambda model: model.with_retry(stop_after_attempt=3))
    .with_model(lambda model: model.bind(seed=42))
)
```

Хук с параметром `prompt` дополнительно получает промпт-клиент Langfuse и может читать всю
конфигурацию промпта, разрешённые ключи или нет. Клиент передаётся копией, так что повлиять на кеш
SDK хук не может.

```python
chain = factory.create("support-reply").with_model(
    lambda model, prompt: model.bind(tools=prompt.config.get("tools", []))
)
```

`with_structured_output(schema)` и `bind_tools(tools)` — сокращённая запись для одноимённых
методов модели:

```python
typed_chain = factory.create("support-reply").with_structured_output(Reply)
tool_chain = factory.create("support-reply").bind_tools([open_ticket])
```

Аргументы модели привязывайте через хук: передать их в `invoke` невозможно, как и в любой цепочке
`prompt | model`.

Каждая копия, возвращённая этими методами, ведёт собственный кеш: собирает свою цепочку и
самостоятельно пересобирается при изменении промпта. Создайте нужные варианты один
раз и используйте их повторно, а не порождайте новый вариант на каждый вызов.

## Хуки для всех цепочек

Хуки, переданные фабрике в параметре `hooks`, применяются ко всем создаваемым ею цепочкам. Так
общие правила, например повторные попытки, задаются один раз на весь процесс:

```python
factory = LangfuseChainFactory(
    client,
    models,
    hooks=[lambda model: model.with_retry(stop_after_attempt=3)],
)
chain = factory.create("support-reply").with_structured_output(Reply)
```

Сначала выполняются хуки самой цепочки, затем хуки фабрики оборачивают полученный результат.
Методам вроде `with_structured_output` нужна сама модель чата, а не обёртка, которую возвращает
`with_retry`. Хук фабрики с параметром `prompt` получает промпт-клиент так же, как хук цепочки, а
копии, возвращённые `with_model` и сокращёнными методами, сохраняют хуки фабрики.

## Имя запуска и трассировка

По умолчанию имя запуска совпадает с именем промпта; `with_config(run_name=...)` позволяет его
переопределить. Цепочка передаёт промпт в метаданных запуска, поэтому обработчик обратных вызовов
Langfuse связывает каждую генерацию с версией промпта:

```python
from langfuse.langchain import CallbackHandler

message = chain.invoke(question, config={"callbacks": [CallbackHandler()]})
```
