# Development

```shell
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run mkdocs serve   # the documentation at http://127.0.0.1:8000
```

Changes are listed in [CHANGELOG.md](https://github.com/rusih100/langfuse-hotswap/blob/main/CHANGELOG.md).
The version comes from the git tag. To release, move the `Unreleased` section of the changelog
under the new version, publish a GitHub Release with a `v*` tag, for example `v0.2.0`, and paste
that section into its notes. The release workflow builds the package and publishes it to PyPI; the
documentation is published to GitHub Pages on every push to `main`. The history of versions is the
[releases page](https://github.com/rusih100/langfuse-hotswap/releases).

The GIF in the README is rendered by `tools/render_demo_gif.py`, a Pillow script that draws a
schematic prompt-management screen frame by frame:
`uv run python tools/render_demo_gif.py docs/assets/demo.gif`. Edit the script and
re-render when the story it tells changes.

The documentation is kept in two languages, `docs/en` and `docs/ru`. A change on one page goes to
its translation in the same change.
