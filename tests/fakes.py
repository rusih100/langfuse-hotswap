"""
Test doubles for the Langfuse client and the chat model.
"""

from __future__ import annotations

import threading

from typing import TYPE_CHECKING, Any, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from langfuse.api import ChatMessage, PlaceholderMessage, Prompt_Chat, Prompt_Text
from langfuse.model import ChatPromptClient, PromptClient, TextPromptClient
from pydantic import ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from uuid import UUID

    from langchain_core.callbacks import CallbackManagerForLLMRun
    from langchain_core.tools import BaseTool
    from pydantic import BaseModel


class FakeChatModel(BaseChatModel):
    """
    Chat model that answers ``model|temperature|last message|bound tool names``.
    Like ``ChatOpenAI``, it stores the model name in ``model_name`` behind the alias ``model``.
    """

    model_config = ConfigDict(populate_by_name=True)

    model_name: str = Field(alias="model")
    temperature: float | None = None
    max_tokens: int | None = None

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _parts(self, messages: list[BaseMessage], kwargs: dict[str, Any]) -> list[str]:
        tool_names = ",".join(kwargs.get("tool_names", []))
        return [self.model_name, str(self.temperature), str(messages[-1].content), tool_names]

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        content = "|".join(self._parts(messages, kwargs))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        for index, part in enumerate(self._parts(messages, kwargs)):
            content = part if index == 0 else f"|{part}"
            yield ChatGenerationChunk(message=AIMessageChunk(content=content))

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in tools]
        return cast("Runnable[LanguageModelInput, AIMessage]", self.bind(tool_names=names, **kwargs))

    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, dict[str, Any] | BaseModel]:
        if isinstance(schema, dict):
            key = next(iter(schema["properties"]))
            parse_dict: RunnableLambda[BaseMessage, dict[str, Any]] = RunnableLambda(
                lambda message: {key: message.content}
            )
            return cast("Runnable[LanguageModelInput, dict[str, Any] | BaseModel]", self | parse_dict)
        model_cls = cast("type[BaseModel]", schema)
        field = next(iter(model_cls.model_fields))
        parse: RunnableLambda[BaseMessage, BaseModel] = RunnableLambda(
            lambda message: model_cls(**{field: message.content})
        )
        return cast("Runnable[LanguageModelInput, dict[str, Any] | BaseModel]", self | parse)


class FakeLangfuse:
    """
    Stands in for the Langfuse client. The prompt is assembled from the current attributes on every call.
    A chat message with the ``placeholder`` role becomes a Langfuse placeholder named by its content.
    Like the real client, it refuses to be copied or pickled.
    """

    def __init__(self) -> None:
        self.version = 1
        self.kind = "chat"
        self.messages: list[tuple[str, str]] = [
            ("system", "You are a cook."),
            ("user", "Ingredients of {{dish}}"),
        ]
        self.text = "Ingredients of {{dish}}"
        self.config: Any = {"model": "fake-1", "provider": "fake", "temperature": 0.1}
        self.error: Exception | None = None
        self.calls: list[dict[str, Any]] = []
        self.threads: list[int] = []

    def __deepcopy__(self, memo: dict[int, Any]) -> FakeLangfuse:
        raise TypeError("the Langfuse client cannot be copied")

    def __reduce__(self) -> str:
        raise TypeError("the Langfuse client cannot be pickled")

    def get_prompt(self, name: str, **kwargs: Any) -> PromptClient:
        self.calls.append({"name": name, **kwargs})
        self.threads.append(threading.get_ident())
        if self.error is not None:
            raise self.error
        if kwargs.get("fallback") is not None:
            raise AssertionError("the fake does not emulate the SDK fallback")
        common: dict[str, Any] = {
            "name": name,
            "version": self.version,
            "config": self.config,
            "labels": [],
            "tags": [],
        }
        if self.kind == "text":
            return TextPromptClient(Prompt_Text(type="text", prompt=self.text, **common))
        messages: list[ChatMessage | PlaceholderMessage] = [
            PlaceholderMessage(type="placeholder", name=content)
            if role == "placeholder"
            else ChatMessage(role=role, content=content)
            for role, content in self.messages
        ]
        return ChatPromptClient(Prompt_Chat(type="chat", prompt=messages, **common))


class RecordingHandler(BaseCallbackHandler):
    """
    Records the name and the metadata of every chain run.
    """

    def __init__(self) -> None:
        self.chain_starts: list[tuple[str | None, dict[str, Any]]] = []

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.chain_starts.append((kwargs.get("name"), metadata or {}))
