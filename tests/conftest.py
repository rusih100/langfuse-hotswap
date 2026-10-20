"""
Fixtures: the fake Langfuse client, a factory over it with one fake model and a record of the builds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

from langfuse_hotswap import LangfuseChainFactory

from .fakes import FakeChatModel, FakeLangfuse

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langfuse.model import PromptClient


@pytest.fixture
def client() -> FakeLangfuse:
    """
    Fake Langfuse client serving the chat prompt ``culinary`` with the ``fake`` provider.
    """

    return FakeLangfuse()


@pytest.fixture
def factory(client: FakeLangfuse) -> LangfuseChainFactory:
    """
    Factory over the fake client with the model ``fake`` and every config key allowed.
    """

    return LangfuseChainFactory(cast("Any", client), {"fake": FakeChatModel(model="fake-0")}, allowed_config_keys="any")


@pytest.fixture
def builds(factory: LangfuseChainFactory, monkeypatch: pytest.MonkeyPatch) -> list[PromptClient]:
    """
    Records the prompt of every model build of ``factory``.
    """

    prompts: list[PromptClient] = []
    model_for = factory._model_for

    def recording(prompt: PromptClient) -> BaseChatModel:
        prompts.append(prompt)
        return model_for(prompt)

    monkeypatch.setattr(factory, "_model_for", recording)
    return prompts
