"""
Chat prompt template that renders Langfuse prompts with the Langfuse substitution rules or a LangChain format.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, cast

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, ChatMessage, HumanMessage, SystemMessage
from langchain_core.messages.utils import convert_to_messages
from langchain_core.prompts.chat import BaseChatPromptTemplate
from langchain_core.prompts.string import DEFAULT_FORMATTER_MAPPING, get_template_variables
from langfuse.model import TemplateParser

if TYPE_CHECKING:
    from langfuse.model import PromptClient

TemplateFormat = Literal["langfuse", "f-string", "mustache", "jinja2"]


class LangfusePromptTemplate(BaseChatPromptTemplate):
    """
    Renders the messages of a Langfuse prompt.

    ``langfuse`` renders with the SDK ``TemplateParser``: a variable is whatever stands between
    ``{{`` and the next ``}}``, stripped. The other formats are the LangChain ones. A text prompt is
    a single human message. A placeholder is filled from the input variable of the same name, which
    holds a list of messages. Roles LangChain does not know become ``ChatMessage`` with that role.
    """

    messages: list[dict[str, str]]
    template_format: TemplateFormat = "langfuse"

    @classmethod
    def from_prompt(cls, prompt: PromptClient, template_format: TemplateFormat = "langfuse") -> LangfusePromptTemplate:
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
                names = cls._variables(message["content"], template_format)
            variables.extend(name for name in names if name not in variables)

        return cls(
            messages=messages,
            template_format=template_format,
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
                result.append(
                    self._message(message["role"], self._render(message["content"], kwargs, self.template_format))
                )
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

    @staticmethod
    def _variables(content: str, template_format: TemplateFormat) -> list[str]:
        """
        Returns the variables of ``content`` in the order the template engine reports them.
        """

        if template_format == "langfuse":
            return TemplateParser.find_variable_names(content)
        return get_template_variables(content, template_format)

    @staticmethod
    def _render(content: str, values: dict[str, Any], template_format: TemplateFormat) -> str:
        """
        Renders ``content`` with ``values`` through the template engine.
        """

        if template_format == "langfuse":
            return TemplateParser.compile_template(content, values)
        return DEFAULT_FORMATTER_MAPPING[template_format](content, **values)

    @staticmethod
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
