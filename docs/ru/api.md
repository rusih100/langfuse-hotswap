# Справочник API

Всё перечисленное импортируется из `langfuse_hotswap`.

## `LangfuseChainFactory`

```python
LangfuseChainFactory(
    client: Langfuse,
    models: Mapping[str, BaseChatModel],
    *,
    allowed_config_keys: Iterable[str] | Literal["any"] | None = None,
    label: str | None = None,
    template_format: Literal["langfuse", "f-string", "mustache", "jinja2"] = "langfuse",
)
```

| Аргумент | Значение |
|---|---|
| `client` | Клиент Langfuse, обычно `langfuse.get_client()`. |
| `models` | Имя → чат-модель. Конфигурация промпта выбирает одну из них ключом `provider`. Не может быть пустым. |
| `allowed_config_keys` | Ключи конфигурации, которым разрешено переопределять поля модели: `None` — ни одному, набор или `"any"`. Строка, отличная от `"any"`, вызывает `TypeError`. |
| `label` | Метка промпта, которую `create` использует без своих `label` и `version`. |
| `template_format` | Движок рендера для промптов, в конфигурации которых ключ `template_format` не задан или не разрешён. |

### `create`

```python
factory.create(prompt_name: str, *, label: str | None = None, version: int | None = None, **get_prompt_kwargs) -> LangfusePromptRunnable[BaseMessage]
```

`label` вместе с `version` вызывают `ValueError`, как и пустое имя. `fallback` вызывает
`TypeError`. Все остальные именованные аргументы уходят в `client.get_prompt`.

## `LangfusePromptRunnable`

`Runnable[dict[str, Any], Output]`. На вход — словарь переменных промпта; `Output` — `BaseMessage`,
пока хук не изменит его.

| Метод | Возвращает |
|---|---|
| `invoke`, `ainvoke`, `stream`, `astream`, `batch`, `abatch`, `astream_events`, `transform`, ... | Интерфейс `Runnable` LangChain. `batch` и его варианты унаследованы. |
| `with_model(hook)` | Копию, в которой модель заменяется на `hook(model)` при каждой пересборке. Хук с параметром `prompt` получает также копию промпт-клиента. |
| `with_structured_output(schema, **kwargs)` | Копию, разбирающую ответ через `model.with_structured_output`. |
| `bind_tools(tools, **kwargs)` | Копию с инструментами, привязанными через `model.bind_tools`. |
| `get_input_schema()`, `get_output_schema()` | Схему текущей цепочки или разрешающую, когда Langfuse недоступен. Получает промпт и собирает цепочку. |
| `copy.copy`, `copy.deepcopy` | Копию, которая разделяет клиент и хуки и начинает с пустым кешем. |

## `LangfusePromptTemplate`

`BaseChatPromptTemplate` поверх сообщений промпта Langfuse.
`LangfusePromptTemplate.from_prompt(prompt, template_format="langfuse")` собирает его и прикрепляет
промпт как `metadata["langfuse_prompt"]`. См. раздел [Шаблоны](templates.md).

## `PromptManager`

```python
PromptManager(client: Langfuse, prompt_name: str, prompt_kwargs: Mapping[str, Any])
```

| Член | Значение |
|---|---|
| `name` | Имя промпта. |
| `resolve(build)` | Получает промпт и возвращает значение, которое `build(prompt)` создал для него, пересобирая при смене промпта. |
| `aresolve(build, config)` | То же без блокировки цикла событий на HTTP. |
| `copy()` | Менеджер того же промпта с пустым кешем. |

`build` должен выбрасывать `ChainBuildError` при ошибке; любое другое исключение проходит наверх.

## Ошибки

| Класс | Когда выбрасывается |
|---|---|
| `HotswapError` | Базовый класс двух следующих. |
| `PromptFetchError` | Промпт не удалось получить, а собранной цепочки нет. Ошибка SDK — в `__cause__`. |
| `ChainBuildError` | Цепочку не удалось собрать, а предыдущей нет. Исходная ошибка — в `__cause__`. |
