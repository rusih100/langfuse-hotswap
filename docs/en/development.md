# Development

```shell
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run mkdocs serve   # the documentation at http://127.0.0.1:8000
```

Changes are listed in [CHANGELOG.md](https://github.com/rusih100/langfuse-hotswap/blob/main/CHANGELOG.md).
The version comes from the git tag. To release, move the `Unreleased` section of the changelog
under the new version, publish a GitHub Release with a `v*` tag, for example `v0.3.0`, and paste
that section into its notes. The release workflow builds the package and publishes it to PyPI; the
documentation is published to GitHub Pages on every push to `main`. The history of versions is the
[releases page](https://github.com/rusih100/langfuse-hotswap/releases).

The GIF in the README is rendered by `tools/render_demo_gif.py`, a Pillow script that draws a
schematic prompt-management screen frame by frame:
`uv run python tools/render_demo_gif.py docs/assets/demo.gif`. Edit the script and
re-render when the story it tells changes.

The documentation is kept in two languages, `docs/en` and `docs/ru`. A change on one page goes to
its translation in the same change.

## The contract with the Langfuse SDK

The library relies on behavior of the Langfuse SDK that its public API does not promise: the
fields of the prompt client, that a fresh cache entry is served as the same object, that a stale
one is served at once while the refresh runs in the background, and the rules of the
`TemplateParser` the library renders with. `tests/test_sdk_contract.py` pins each of these against
a real client with a stubbed HTTP API, so a change in the SDK fails the build instead of changing
the behavior silently. CI runs the suite on the lowest supported `langfuse` and on the locked
version; a nightly workflow runs it on the latest `langfuse` 4.x and 5.x releases.
