"""
Chat prompt template that renders Langfuse prompts with the Langfuse substitution rules.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any, NamedTuple, cast

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, ChatMessage, HumanMessage, SystemMessage
from langchain_core.messages.utils import convert_to_messages
from langchain_core.prompts.chat import BaseChatPromptTemplate

if TYPE_CHECKING:
    from langfuse.model import PromptClient


class _Variable(NamedTuple):
    """
    A ``{{ name }}`` occurrence: the stripped name and the slice of the template it occupies.
    """

    name: str
    start: int
    end: int


class LangfusePromptTemplate(BaseChatPromptTemplate):
    """
    Renders the messages of a Langfuse prompt with the Langfuse substitution rules.

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
        if isinstance(prompt.prompt, str):
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
                names = [variable.name for variable in _variables(message["content"])]
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
                result.append(_message(message["role"], _render(message["content"], kwargs)))
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


def _render(content: str, values: Mapping[str, Any]) -> str:
    """
    Replaces every variable of ``content`` found in ``values`` with ``str(value)``, ``None`` with
    an empty string. Variables missing from ``values`` are left as they are.
    """

    parts: list[str] = []
    index = 0
    for variable in _variables(content):
        parts.append(content[index : variable.start])
        if variable.name in values:
            value = values[variable.name]
            parts.append("" if value is None else str(value))
        else:
            parts.append(content[variable.start : variable.end])
        index = variable.end
    parts.append(content[index:])

    return "".join(parts)


def _variables(content: str) -> Iterator[_Variable]:
    """
    Yields the variables of ``content`` in order of appearance.
    """

    index = 0
    while (start := content.find("{{", index)) != -1:
        close = content.find("}}", start)
        if close == -1:
            return
        index = close + 2
        yield _Variable(content[start + 2 : close].strip(), start, index)


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
