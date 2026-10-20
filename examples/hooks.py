"""
Customize the model with hooks that run on every rebuild.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI
from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel, LanguageModelInput
    from langchain_core.messages import BaseMessage
    from langchain_core.runnables import Runnable
    from langfuse.model import PromptClient


def tools_from_config(model: BaseChatModel, prompt: PromptClient) -> Runnable[LanguageModelInput, BaseMessage]:
    """
    Binds the tool definitions listed under ``tools`` in the prompt config.
    """

    tools = prompt.config.get("tools")
    return model.bind_tools(tools) if tools else model


factory = LangfuseChainFactory(get_client(), models={"openai": ChatOpenAI(model="gpt-5.5")})
chain = (
    factory.create("support-reply")
    .with_model(lambda model: model.with_retry(stop_after_attempt=3))
    .with_model(lambda model: model.bind(seed=42))
    .with_model(tools_from_config)
)

message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"})
print(message.content)
