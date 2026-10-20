# Версии промптов

Метод `create` принимает `label` или `version`. Без обоих действует `label` фабрики, а без него —
метка `production`.

```python
staging = LangfuseChainFactory(langfuse, models=models, label="staging")

chain = staging.create("support-reply")  # label "staging"
live = staging.create("support-reply", label="production")
pinned = staging.create("support-reply", version=12)  # the factory label does not apply
```

Все остальные именованные аргументы `create` — `cache_ttl_seconds`, `max_retries`,
`fetch_timeout_seconds` и прочие — передаются в `client.get_prompt` как есть:

```python
chain = factory.create("support-reply", cache_ttl_seconds=30)
```

## Кеш и реплики

SDK кеширует каждый промпт и обновляет его в фоне по истечении `cache_ttl_seconds`, по умолчанию
60 секунд. Перенос метки доходит до работающего сервиса в пределах этого времени, а до тех пор
реплики могут работать с разными версиями. При `cache_ttl_seconds=0` промпт запрашивается на каждый
вызов.

## Прогрев

Первый вызов цепочки получает промпт по HTTP и собирает `template | model`. Параллельные первые
вызовы запрашивают промпт один раз. Чтобы снять это с первого запроса, прогрейте цепочку при
запуске:

```python
chain.get_input_schema()  # fetches the prompt and builds the chain
```

Холодный старт при недоступном Langfuse выбрасывает `PromptFetchError`; про локальную запасную
цепочку см. раздел [Обработка ошибок](errors.md#promptfetcherror).
