# Разработка

```shell
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run mkdocs serve   # документация по адресу http://127.0.0.1:8000
```

История изменений ведётся в
[CHANGELOG.md](https://github.com/rusih100/langfuse-hotswap/blob/main/CHANGELOG.md). Версия
пакета определяется по git-тегу. Чтобы выпустить новую версию, перенесите раздел `Unreleased`
в раздел с номером версии, опубликуйте GitHub Release с тегом вида `v*` (например, `v0.2.0`) и
скопируйте этот раздел в описание релиза. Workflow релиза соберёт пакет и опубликует его на PyPI;
документация публикуется на GitHub Pages при каждом push в `main`. Список выпущенных версий — на
[странице релизов](https://github.com/rusih100/langfuse-hotswap/releases).

GIF в README генерируется скриптом `tools/render_demo_gif.py` — он покадрово отрисовывает
схематичный экран управления промптами средствами Pillow:
`uv run python tools/render_demo_gif.py docs/assets/demo.gif`. При изменении
сценария отредактируйте скрипт и перегенерируйте файл.

Документация ведётся на двух языках: `docs/en` и `docs/ru`. Изменение на любой странице вносится
в её перевод в рамках того же изменения.
