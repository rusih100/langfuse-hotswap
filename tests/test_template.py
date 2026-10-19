"""
Rendering of Langfuse prompts: variables, placeholders, roles and the input schema.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

from langchain_core.messages import HumanMessage

from .fakes import RecordingHandler

if TYPE_CHECKING:
    from langfuse_hotswap import LangfuseChainFactory

    from .fakes import FakeLangfuse


# Messages


def test_text_prompt_becomes_human_message(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A text prompt is rendered as one human message and carries the prompt in the metadata.
    """

    client.kind = "text"
    handler = RecordingHandler()

    result = factory.create("culinary").invoke({"dish": "borscht"}, config={"callbacks": [handler]})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert any(m.get("langfuse_prompt") is not None for _, m in handler.chain_starts)


def test_chat_prompt_placeholder_becomes_messages_placeholder(
    factory: LangfuseChainFactory, client: FakeLangfuse
) -> None:
    """
    A placeholder is filled with the messages from the input variable of the same name.
    """

    client.messages = [("system", "You are a cook."), ("placeholder", "history"), ("user", "Ingredients of {{dish}}")]
    chain = factory.create("culinary")

    result = chain.invoke({"dish": "borscht", "history": [HumanMessage("hi")]})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert set(cast("Any", chain.get_input_schema()).model_json_schema()["properties"]) == {"dish", "history"}


def test_placeholder_rejects_a_string(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A placeholder filled with a string instead of a list of messages raises TypeError.
    """

    client.messages = [("placeholder", "history"), ("user", "Ingredients of {{dish}}")]

    with pytest.raises(TypeError, match="'history' must be a list"):
        factory.create("culinary").invoke({"dish": "borscht", "history": "hi"})


def test_developer_role_is_kept(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A role LangChain does not know, such as developer, is rendered and is not a variable.
    """

    client.messages = [("developer", "Be terse."), ("user", "Ingredients of {{dish}}")]
    handler = RecordingHandler()

    result = factory.create("culinary").invoke({"dish": "borscht"}, config={"callbacks": [handler]})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert set(cast("Any", factory.create("culinary").get_input_schema()).model_json_schema()["properties"]) == {"dish"}


def test_pretty_repr(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    pretty_repr lists the messages with their roles and the placeholders by name.
    """

    client.messages = [("system", "You are a cook."), ("placeholder", "history"), ("user", "{{dish}}")]
    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht", "history": []})

    assert chain._built is not None
    prompt = cast("Any", chain._built[1].get_prompts()[0])
    assert prompt.pretty_repr() == "system: You are a cook.\n[placeholder history]\nuser: {{dish}}"


# Variables


def test_single_braces_and_html_are_left_untouched(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Single braces, quotes and HTML are left as they are, only {{ }} variables are replaced.
    """

    client.messages = [("user", 'JSON {"a": 1}, LaTeX \\frac{a}{b}, name {{ name }}')]

    result = factory.create("culinary").invoke({"name": 'O"Neil <b>'})

    assert result.content == 'fake-1|0.1|JSON {"a": 1}, LaTeX \\frac{a}{b}, name O"Neil <b>|'


def test_rendering_matches_langfuse_compile(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Rendering follows the Langfuse TemplateParser rules for odd names, None and non-string values.
    """

    client.messages = [("user", "{{a.b}} {{{raw}}} {{#flag}}x{{/flag}} {{n}} {{none}} {{items}}")]
    chain = factory.create("culinary")
    inputs = {"a.b": "flat", "{raw": "R", "#flag": "", "/flag": "", "n": 1, "none": None, "items": [1, 2]}

    result = chain.invoke(inputs)

    assert result.content == "fake-1|0.1|flat R} x 1  [1, 2]|"
    assert set(cast("Any", chain.get_input_schema()).model_json_schema()["properties"]) == set(inputs)


def test_mustache_sections_are_variables_not_sections(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Mustache sections are not supported: {{#flag}} is a variable named #flag.
    """

    client.messages = [("user", "{{#flag}}yes{{/flag}}")]

    with pytest.raises(KeyError, match="#flag"):
        factory.create("culinary").invoke({"flag": True})


def test_variable_names_follow_the_langfuse_rule(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A variable name is the stripped text between the braces, spaces and dashes included.
    """

    client.messages = [("user", "{{ my-var }} {{user name}}")]

    result = factory.create("culinary").invoke({"my-var": "<a>", "user name": "<b>"})

    assert result.content == "fake-1|0.1|<a> <b>|"


def test_missing_variable_raises(factory: LangfuseChainFactory) -> None:
    """
    A missing variable raises KeyError that names it.
    """

    with pytest.raises(KeyError, match="dish"):
        factory.create("culinary").invoke({})


# Input schema


def test_input_schema_lists_prompt_variables(factory: LangfuseChainFactory) -> None:
    """
    The input schema lists the prompt variables.
    """

    schema = cast("Any", factory.create("culinary").get_input_schema()).model_json_schema()

    assert "dish" in schema["properties"]


def test_input_schema_does_not_require_langfuse(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Without Langfuse the input schema falls back to a permissive object.
    """

    client.error = ConnectionError("boom")

    schema = cast("Any", factory.create("culinary").get_input_schema()).model_json_schema()

    assert schema["type"] == "object"


def test_output_schema_falls_back_without_langfuse(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Without Langfuse the output schema falls back to the default one.
    """

    client.error = ConnectionError("boom")

    schema = cast("Any", factory.create("culinary").get_output_schema())

    assert schema.model_json_schema()
