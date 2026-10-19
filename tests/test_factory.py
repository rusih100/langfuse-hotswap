"""
The factory: create arguments and the shared kwargs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

from langfuse_hotswap import LangfuseChainFactory, LangfusePromptRunnable, PromptFetchError

if TYPE_CHECKING:
    from .fakes import FakeLangfuse


# Factory


def test_create_returns_runnable(factory: LangfuseChainFactory) -> None:
    """
    create returns a working LangfusePromptRunnable.
    """

    chain = factory.create("culinary")

    assert isinstance(chain, LangfusePromptRunnable)
    assert chain.invoke({"dish": "borscht"}).content == "fake-1|0.1|Ingredients of borscht|"


def test_label_is_passed_to_get_prompt(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    label reaches get_prompt and version stays unset.
    """

    factory.create("culinary", label="staging").invoke({"dish": "borscht"})

    assert client.calls[0]["label"] == "staging"
    assert client.calls[0]["version"] is None


def test_version_is_passed_to_get_prompt(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    version reaches get_prompt and label stays unset.
    """

    factory.create("culinary", version=3).invoke({"dish": "borscht"})

    assert client.calls[0]["version"] == 3
    assert client.calls[0]["label"] is None


def test_label_and_version_together_are_rejected_at_create(factory: LangfuseChainFactory) -> None:
    """
    label and version together are rejected by create.
    """

    with pytest.raises(ValueError, match="label and version"):
        factory.create("culinary", label="staging", version=3)


def test_empty_prompt_name_is_rejected_at_create(factory: LangfuseChainFactory) -> None:
    """
    An empty prompt name is rejected by create.
    """

    with pytest.raises(ValueError, match="empty"):
        factory.create("")


def test_get_prompt_options_are_passed_through(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    cache_ttl_seconds, max_retries and fetch_timeout_seconds reach get_prompt.
    """

    factory.create("culinary", cache_ttl_seconds=300, max_retries=1, fetch_timeout_seconds=2).invoke({"dish": "x"})

    assert client.calls[0]["cache_ttl_seconds"] == 300
    assert client.calls[0]["max_retries"] == 1
    assert client.calls[0]["fetch_timeout_seconds"] == 2
    assert client.calls[0]["fallback"] is None


def test_fallback_type_follows_its_shape(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A string fallback requests a text prompt, a list of messages requests a chat prompt.
    """

    text = factory.create("culinary", fallback="Ingredients of {{dish}}")
    chat = factory.create("culinary", fallback=[{"role": "user", "content": "Ingredients of {{dish}}"}])

    with pytest.raises(PromptFetchError, match="does not emulate"):
        text.invoke({"dish": "x"})
    with pytest.raises(PromptFetchError, match="does not emulate"):
        chat.invoke({"dish": "x"})
    assert client.calls[0]["type"] == "text"
    assert client.calls[0]["fallback"] == "Ingredients of {{dish}}"
    assert client.calls[1]["type"] == "chat"


def test_allowed_config_keys_rejects_a_string(client: FakeLangfuse) -> None:
    """
    A string as allowed_config_keys is rejected instead of being split into characters.
    """

    with pytest.raises(TypeError):
        LangfuseChainFactory(cast("Any", client), allowed_config_keys="model")


def test_model_kwargs_reach_init_chat_model(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    Factory kwargs reach init_chat_model and override the config.
    """

    http_client = object()
    factory = LangfuseChainFactory(
        cast("Any", client), allowed_config_keys=None, http_client=http_client, temperature=0.9
    )

    factory.create("culinary").invoke({"dish": "borscht"})

    assert init_calls == [{**client.config, "http_client": http_client, "temperature": 0.9}]


def test_created_runnables_are_independent(factory: LangfuseChainFactory, init_calls: list[dict[str, Any]]) -> None:
    """
    Runnables created by one factory build their own chains.
    """

    first = factory.create("culinary")
    second = factory.create("culinary")

    first.invoke({"dish": "borscht"})
    first.invoke({"dish": "borscht"})
    second.invoke({"dish": "borscht"})

    assert len(init_calls) == 2
