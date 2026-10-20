# langfuse-hotswap

*Горячая замена языковой модели в цепочке LangChain через промпт Langfuse.*

[![PyPI](https://img.shields.io/pypi/v/langfuse-hotswap)](https://pypi.org/project/langfuse-hotswap/)
[![Python](https://img.shields.io/pypi/pyversions/langfuse-hotswap)](https://pypi.org/project/langfuse-hotswap/)
[![CI](https://github.com/rusih100/langfuse-hotswap/actions/workflows/ci.yml/badge.svg)](https://github.com/rusih100/langfuse-hotswap/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/rusih100/langfuse-hotswap/blob/main/LICENSE)

[English](README.md) | **Русский**

**Документация**: <https://rusih100.github.io/langfuse-hotswap/ru/>

<p align="center">
  <img src="docs/assets/demo.gif" width="800" alt="Сервис отвечает в цикле; метку production переносят на другую версию, и следующий ответ приходит от другой модели">
</p>

Управление промптами в [Langfuse](https://langfuse.com) выносит шаблон из кода: его правят в
интерфейсе, а сервис забирает актуальную версию. Модель при этом остаётся в коде — `gpt-5.5`,
`temperature=0.2` прописаны рядом с цепочкой, и любое их изменение требует деплоя.

`langfuse-hotswap` переносит модель в конфигурацию промпта. Чат-модели вы создаёте в коде, а
библиотека предоставляет обычный [LangChain](https://github.com/langchain-ai/langchain)
`Runnable`: при каждом вызове он получает промпт, выбирает по его конфигурации модель и параметры
и пересобирает цепочку, когда промпт меняется. Версия промпта объединяет шаблон, модель и
параметры — они получают метку, выкатываются и откатываются как единое целое.

- **Любая чат-модель LangChain.** `ChatOpenAI`, `ChatAnthropic`, `ChatOllama`, ... создаются в
  коде и выбираются из конфигурации по имени.
- **Только явно разрешённое.** Конфигурация меняет лишь те поля модели, которые разрешил код, и
  ничего, пока он этого не сделал. Ключи, адреса и HTTP-клиенты остаются в коде.
- **Устойчивость к сбоям.** Если новая версия не собирается или Langfuse недоступен, продолжает
  работать последняя исправная цепочка.
- **Полноценный `Runnable`.** `invoke`, `stream`, `batch` и их асинхронные варианты,
  `with_structured_output`, `bind_tools`, композиция с другими runnable.
- **Асинхронность без блокировок.** Прогретый кеш SDK читается в цикле событий, HTTP-запросы
  выполняются в пуле потоков.
- **Правила подстановки Langfuse** — или `f-string`, `mustache` и `jinja2` по запросу.
- **Трассировка привязана к версии промпта.**

## Установка

```shell
pip install langfuse-hotswap langchain-openai langchain-anthropic
```

## Пример

Создайте в Langfuse чат-промпт `support-reply`, присвойте ему метку `production` и задайте
конфигурацию:

```json
{"provider": "openai", "model": "gpt-5.5", "temperature": 0.2, "max_tokens": 800}
```

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

message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"})
print(message.content)
```

Теперь создайте новую версию промпта с параметрами `"provider": "anthropic", "model":
"claude-sonnet-5-5"` и перенесите на неё метку `production`. Следующий вызов `invoke`
уйдёт в Anthropic. Верните метку обратно — и запросы снова пойдут в OpenAI. Без перезапуска и без
деплоя.


## Границы доверия

Конфигурацией промпта управляет каждый, кто может его редактировать. Насколько далеко простирается
это право, решает код:

```python
factory = LangfuseChainFactory(
    get_client(),
    models={"openai": ChatOpenAI(api_key=..., timeout=30)},  # built here, credentials included
    allowed_config_keys={"model", "temperature", "max_tokens"},  # the only keys the config may change
)
```

`provider` выбирает одну из моделей. Без `allowed_config_keys` конфигурация больше ничего не
меняет; со значением `"any"` она меняет всё, включая `base_url` и `api_key`. Подробнее — в разделе
[Безопасность](https://rusih100.github.io/langfuse-hotswap/ru/security/).

## Что дальше

- [Понятия](https://rusih100.github.io/langfuse-hotswap/ru/concepts/): пять частей библиотеки на одной странице.
- [Модели и ключи конфигурации](https://rusih100.github.io/langfuse-hotswap/ru/models/): что конфигурация промпта может менять и как.
- [Настройка модели](https://rusih100.github.io/langfuse-hotswap/ru/customizing/): хуки, структурированный вывод, инструменты.
- [Как это работает](https://rusih100.github.io/langfuse-hotswap/ru/how-it-works/): получение промпта, сравнение, пересборка, сбои, асинхронный путь.
- [Справочник API](https://rusih100.github.io/langfuse-hotswap/ru/api/).
- [`examples/`](examples/): короткие скрипты, по одному на каждую возможность.

Неофициальный проект, не связанный с Langfuse и LangChain. Лицензия MIT.
