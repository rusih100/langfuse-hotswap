"""
Fixtures. ``init_chat_model`` is replaced with a fake that records its parameters and returns ``FakeChatModel``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

from langfuse_hotswap import LangfuseChainFactory

from .fakes import FakeChatModel, FakeLangfuse

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


@pytest.fixture
def init_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """
    Records the parameters passed to ``init_chat_model`` and returns ``FakeChatModel`` instead of a real model.
    """

    calls: list[dict[str, Any]] = []

    def fake_init_chat_model(model: str, *, model_provider: str | None = None, **kwargs: Any) -> BaseChatModel:
        calls.append({"model": model, "model_provider": model_provider, **kwargs})
        if kwargs.get("fail"):
            raise RuntimeError("provider is down")
        return FakeChatModel(model=model, temperature=kwargs.get("temperature"), max_tokens=kwargs.get("max_tokens"))

    monkeypatch.setattr("langfuse_hotswap._runnable.init_chat_model", fake_init_chat_model)
    return calls


@pytest.fixture
def client() -> FakeLangfuse:
    """
    Fake Langfuse client serving the chat prompt ``culinary`` with the ``fake`` provider.
    """

    return FakeLangfuse()


@pytest.fixture
def factory(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> LangfuseChainFactory:
    """
    Factory over the fake client with the allowlist disabled, so every unblocked config key reaches the model.
    """

    return LangfuseChainFactory(cast("Any", client), allowed_config_keys=None)
