"""
The behavior of the Langfuse SDK the library relies on, checked against a real client with a stubbed HTTP API.
"""

from __future__ import annotations

import threading
import time
import uuid

from typing import TYPE_CHECKING, Any

import pytest

from langfuse import Langfuse
from langfuse._utils.prompt_cache import PromptCacheItem
from langfuse.api import ChatMessage, PlaceholderMessage, Prompt_Chat, Prompt_Text
from langfuse.model import TemplateParser

if TYPE_CHECKING:
    from collections.abc import Iterator


class StubPromptsApi:
    """
    Stands in for ``client.api.prompts``: serves ``prompt`` on ``get`` and records every request.
    """

    def __init__(self, prompt: Prompt_Chat | Prompt_Text) -> None:
        self.prompt = prompt
        self.error: Exception | None = None
        self.gate: threading.Event | None = None
        self.calls: list[str] = []

    def get(self, name: str, **kwargs: Any) -> Prompt_Chat | Prompt_Text:
        self.calls.append(name)
        if self.gate is not None:
            self.gate.wait(5)
        if self.error is not None:
            raise self.error
        return self.prompt

    def create(self, request: object) -> Prompt_Chat | Prompt_Text:
        return self.prompt


def chat_prompt(name: str = "support", version: int = 1, model: str = "fake-1") -> Prompt_Chat:
    """
    Builds a chat prompt response with a system message, a placeholder and a user message.
    """

    return Prompt_Chat(
        type="chat",
        name=name,
        version=version,
        config={"model": model},
        labels=["production"],
        tags=[],
        prompt=[
            ChatMessage(role="system", content="You are a cook."),
            PlaceholderMessage(type="placeholder", name="history"),
            ChatMessage(role="user", content="Ingredients of {{dish}}"),
        ],
    )


@pytest.fixture
def api() -> StubPromptsApi:
    """
    Stub of the prompts API serving ``support`` version 1.
    """

    return StubPromptsApi(chat_prompt())


@pytest.fixture
def client(api: StubPromptsApi, monkeypatch: pytest.MonkeyPatch) -> Iterator[Langfuse]:
    """
    Real Langfuse client with tracing disabled, an unreachable host and the prompts API replaced by ``api``.
    """

    client = Langfuse(
        public_key=f"pk-lf-{uuid.uuid4()}",
        secret_key="sk-lf-test",  # noqa: S106
        host="http://127.0.0.1:9",
        tracing_enabled=False,
    )
    monkeypatch.setattr(client.api.prompts, "get", api.get)
    monkeypatch.setattr(client.api.prompts, "create", api.create)
    yield client
    client.shutdown()


def expire_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Moves the clock of the SDK cache far enough ahead that every entry created so far is expired.
    """

    now = PromptCacheItem.get_epoch_seconds()
    monkeypatch.setattr(PromptCacheItem, "get_epoch_seconds", staticmethod(lambda: now + 10**6))


# Prompt client


def test_chat_prompt_client_exposes_the_fields_the_library_reads(client: Langfuse) -> None:
    """
    A fetched chat prompt has name, version, config, is_fallback and the messages as typed dicts.
    """

    prompt = client.get_prompt("support", type="chat")

    assert (prompt.name, prompt.version, prompt.config, prompt.is_fallback) == (
        "support",
        1,
        {"model": "fake-1"},
        False,
    )
    assert prompt.prompt == [
        {"type": "message", "role": "system", "content": "You are a cook."},
        {"type": "placeholder", "name": "history"},
        {"type": "message", "role": "user", "content": "Ingredients of {{dish}}"},
    ]


def test_text_prompt_client_holds_the_template_as_a_string(client: Langfuse, api: StubPromptsApi) -> None:
    """
    A fetched text prompt holds the template in ``prompt`` as a string.
    """

    api.prompt = Prompt_Text(type="text", name="support", version=1, config={}, labels=[], tags=[], prompt="Hi {{x}}")

    prompt = client.get_prompt("support")

    assert prompt.prompt == "Hi {{x}}"
    assert prompt.is_fallback is False


def test_fallback_prompt_is_flagged(client: Langfuse, api: StubPromptsApi) -> None:
    """
    The prompt built from ``fallback`` after a failed fetch has ``is_fallback`` set.
    """

    api.error = ConnectionError("boom")

    prompt = client.get_prompt("support", type="chat", fallback=[{"role": "user", "content": "{{dish}}"}])

    assert prompt.is_fallback is True
    assert prompt.config == {}


# Cache


def test_fresh_cache_returns_the_same_object_without_a_request(client: Langfuse, api: StubPromptsApi) -> None:
    """
    While the cache entry is fresh, get_prompt returns the same object and makes no request.
    """

    first = client.get_prompt("support", type="chat")

    second = client.get_prompt("support", type="chat")

    assert second is first
    assert api.calls == ["support"]


def test_stale_cache_returns_the_old_object_and_refreshes_in_the_background(
    client: Langfuse, api: StubPromptsApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    An expired cache entry is returned as is while the refresh request runs in another thread.
    """

    first = client.get_prompt("support", type="chat")
    expire_cache(monkeypatch)
    api.prompt = chat_prompt(version=2)
    api.gate = threading.Event()

    started = time.monotonic()
    stale = client.get_prompt("support", type="chat")
    elapsed = time.monotonic() - started
    api.gate.set()
    deadline = time.monotonic() + 5
    while client.get_prompt("support", type="chat") is first and time.monotonic() < deadline:
        time.sleep(0.01)

    assert stale is first
    assert elapsed < 1
    assert client.get_prompt("support", type="chat").version == 2


def test_cache_ttl_zero_requests_every_time(client: Langfuse, api: StubPromptsApi) -> None:
    """
    With cache_ttl_seconds=0 every get_prompt makes a request and returns a new object.
    """

    first = client.get_prompt("support", type="chat", cache_ttl_seconds=0)

    second = client.get_prompt("support", type="chat", cache_ttl_seconds=0)

    assert second is not first
    assert api.calls == ["support", "support"]


def test_updating_a_prompt_drops_the_cache_entries_whose_name_starts_with_its_name(
    client: Langfuse, api: StubPromptsApi
) -> None:
    """
    Creating a prompt version through the client drops the cache entries of every prompt whose name starts with it.
    """

    client.get_prompt("support", type="chat")
    client.get_prompt("support-reply", type="chat")
    api.calls.clear()

    client.create_prompt(name="support", prompt=[{"role": "user", "content": "x"}], type="chat")
    client.get_prompt("support-reply", type="chat")

    assert api.calls == ["support-reply"]


# Rendering


@pytest.mark.parametrize(
    ("template", "variables", "rendered"),
    [
        ("Ingredients of {{dish}}", ["dish"], "Ingredients of borscht"),
        ("{{ dish }} and {{dish}}", ["dish", "dish"], "borscht and borscht"),
        ("{{a.b}} {{{raw}}} {{#flag}}x{{/flag}}", ["a.b", "{raw", "#flag", "/flag"], "flat R} x"),
        ("{{n}} {{none}} {{items}}", ["n", "none", "items"], "1  [1, 2]"),
        ("{{ my-var }} {{user name}} {{}}", ["my-var", "user name", ""], "<a> <b> empty"),
        ("unclosed {{dish and {{other}}", ["dish and {{other"], "unclosed {{dish and {{other}}"),
        ('JSON {"a": 1}, LaTeX \\frac{a}{b}', [], 'JSON {"a": 1}, LaTeX \\frac{a}{b}'),
        ("{{missing}} stays", ["missing"], "{{missing}} stays"),
        ("", [], ""),
    ],
)
def test_template_parser_rendering_rules(template: str, variables: list[str], rendered: str) -> None:
    """
    TemplateParser takes the stripped text between {{ and }} as a variable, inserts str(value) without
    escaping, None as an empty string, and leaves missing variables and everything else as is.
    """

    values = {
        "dish": "borscht",
        "a.b": "flat",
        "{raw": "R",
        "#flag": "",
        "/flag": "",
        "n": 1,
        "none": None,
        "items": [1, 2],
        "my-var": "<a>",
        "user name": "<b>",
        "": "empty",
    }

    assert TemplateParser.find_variable_names(template) == variables
    assert TemplateParser.compile_template(template, values) == rendered
