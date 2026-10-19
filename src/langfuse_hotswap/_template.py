"""
Chat prompt template that renders Langfuse prompts with the Langfuse substitution rules.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, ChatMessage, HumanMessage, SystemMessage
from langchain_core.messages.utils import convert_to_messages
from langchain_core.prompts.chat import BaseChatPromptTemplate
from langfuse.model import TemplateParser, TextPromptClient

if TYPE_CHECKING:
    from langfuse.model import PromptClient


class LangfusePromptTemplate(BaseChatPromptTemplate):
    """
    Renders the messages of a Langfuse prompt with the Langfuse ``TemplateParser``.

    A variable is whatever stands between ``{{`` and the next ``}}``, stripped. A text prompt is a
    single human message. A placeholder is filled from the input variable of the same name, which
    holds a list of messages. Roles LangChain does not know become ``ChatMessage`` with that role.
    """

    messages: list[dict[str, str]]

    @classmethod
    def from_prompt(cls, prompt: PromptClient) -> LangfusePromptTemplate:
        """
        Builds the template from ``prompt`` and attaches the prompt as ``metadata["langfuse_prompt"]``.
        """

        messages: list[dict[str, str]]
        if isinstance(prompt, TextPromptClient):
            messages = [{"type": "message", "role": "user", "content": prompt.prompt}]
        else:
            messages = [cast("dict[str, str]", dict(message)) for message in prompt.prompt]

        variables: list[str] = []
        input_types: dict[str, Any] = {}
        for message in messages:
            if message["type"] == "placeholder":
                names = [message["name"]]
                input_types[message["name"]] = list[AnyMessage]
            else:
                names = TemplateParser.find_variable_names(message["content"])
            variables.extend(name for name in names if name not in variables)

        return cls(
            messages=messages,
            input_variables=variables,
            input_types=input_types,
            metadata={"langfuse_prompt": prompt},
        )

    @classmethod
    def is_lc_serializable(cls) -> bool:
        return False

    @property
    def _prompt_type(self) -> str:
        return "langfuse"

    def format_messages(self, **kwargs: Any) -> list[BaseMessage]:
        result: list[BaseMessage] = []
        for message in self.messages:
            if message["type"] != "placeholder":
                content = TemplateParser.compile_template(message["content"], kwargs)
                result.append(_message(message["role"], content))
                continue

            value = kwargs[message["name"]]
            if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
                raise TypeError(
                    f"placeholder {message['name']!r} must be a list of messages, got {type(value).__name__}"
                )
            result.extend(convert_to_messages(value))

        return result

    def pretty_repr(self, html: bool = False) -> str:
        return "\n".join(
            f"[placeholder {message['name']}]"
            if message["type"] == "placeholder"
            else f"{message['role']}: {message['content']}"
            for message in self.messages
        )


def _message(role: str, content: str) -> BaseMessage:
    """
    Maps a Langfuse role to a LangChain message.
    """

    if role == "system":
        return SystemMessage(content)
    if role in ("user", "human"):
        return HumanMessage(content)
    if role in ("assistant", "ai"):
        return AIMessage(content)

    return ChatMessage(content=content, role=role)
