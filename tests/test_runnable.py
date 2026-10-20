"""
The runnable: hooks, tracing, copies and the streaming interface.
"""

from __future__ import annotations

import copy

from typing import TYPE_CHECKING, Any, cast

import pytest

from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from pydantic import BaseModel

from langfuse_hotswap import ChainBuildError, LangfuseChainFactory, PromptFetchError

from .fakes import FakeChatModel, RecordingHandler

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langchain_core.language_models import BaseChatModel, LanguageModelInput
    from langchain_core.messages import BaseMessage
    from langchain_core.runnables import Runnable
    from langfuse.model import PromptClient

    from .fakes import FakeLangfuse


class Answer(BaseModel):
    """
    Structured output schema of the hook tests.
    """

    text: str


# Model hooks


def test_with_structured_output_returns_copy(factory: LangfuseChainFactory) -> None:
    """
    with_structured_output returns a copy that parses into a pydantic model and leaves the original as is.
    """

    chain = factory.create("culinary")
    structured = chain.with_structured_output(Answer)

    assert structured is not chain
    assert structured.invoke({"dish": "borscht"}) == Answer(text="fake-1|0.1|Ingredients of borscht|")
    assert chain.invoke({"dish": "borscht"}).content == "fake-1|0.1|Ingredients of borscht|"


def test_with_structured_output_accepts_dict_schema(factory: LangfuseChainFactory) -> None:
    """
    with_structured_output accepts a JSON schema dict.
    """

    structured = factory.create("culinary").with_structured_output({"title": "Answer", "properties": {"text": {}}})

    assert structured.invoke({"dish": "borscht"}) == {"text": "fake-1|0.1|Ingredients of borscht|"}


def test_bind_tools_returns_copy(factory: LangfuseChainFactory) -> None:
    """
    bind_tools returns a copy with the tools bound and leaves the original as is.
    """

    @tool
    def search(query: str) -> str:
        """
        Searches the web.
        """

        return query

    chain = factory.create("culinary")
    with_tools = chain.bind_tools([search])

    assert with_tools is not chain
    assert with_tools.invoke({"dish": "borscht"}).content == "fake-1|0.1|Ingredients of borscht|search"
    assert chain.invoke({"dish": "borscht"}).content == "fake-1|0.1|Ingredients of borscht|"


def test_with_model_wraps_the_model(factory: LangfuseChainFactory) -> None:
    """
    with_model receives the model and its result replaces the model.
    """

    seen: list[str] = []

    def hook(model: BaseChatModel) -> Runnable[LanguageModelInput, BaseMessage]:
        seen.append(type(model).__name__)
        return model.bind(tool_names=["wrapped"])

    result = factory.create("culinary").with_model(hook).invoke({"dish": "borscht"})

    assert seen == ["FakeChatModel"]
    assert result.content == "fake-1|0.1|Ingredients of borscht|wrapped"


def test_with_model_hook_can_read_the_prompt(client: FakeLangfuse) -> None:
    """
    A hook with a prompt parameter, positional or keyword-only, receives the prompt with the full config.
    """

    factory = LangfuseChainFactory(
        cast("Any", client), {"fake": FakeChatModel(model="fake-0")}, allowed_config_keys={"model"}
    )
    client.config = {"model": "fake-1", "provider": "fake", "tools": ["search", "code"]}

    chain = factory.create("culinary").with_model(lambda model, prompt: model.bind(tool_names=prompt.config["tools"]))
    chain_kw = factory.create("culinary").with_model(lambda m, *, prompt: m.bind(tool_names=prompt.config["tools"]))

    assert chain.invoke({"dish": "borscht"}).content == "fake-1|None|Ingredients of borscht|search,code"
    assert chain_kw.invoke({"dish": "borscht"}).content == "fake-1|None|Ingredients of borscht|search,code"


def test_with_model_hook_without_prompt_parameter_gets_only_the_model(factory: LangfuseChainFactory) -> None:
    """
    A hook without a prompt parameter is called with the model only.
    """

    def hook(model: BaseChatModel, max_retries: int = 3) -> Runnable[LanguageModelInput, BaseMessage]:
        assert max_retries == 3
        return model.bind(tool_names=[str(max_retries)])

    assert factory.create("culinary").with_model(hook).invoke({"dish": "borscht"}).content.endswith("|3")


def test_hook_gets_a_copy_of_the_prompt(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A hook that mutates the prompt does not change the cached prompt.
    """

    def hook(model: BaseChatModel, prompt: PromptClient) -> Runnable[LanguageModelInput, BaseMessage]:
        prompt.config["mutated"] = True
        return model

    factory.create("culinary").with_model(hook).invoke({"dish": "borscht"})

    assert "mutated" not in client.config


def test_hook_raising_is_a_build_error(factory: LangfuseChainFactory) -> None:
    """
    An exception raised by a hook becomes ChainBuildError.
    """

    def hook(model: BaseChatModel) -> Runnable[LanguageModelInput, BaseMessage]:
        raise RuntimeError("hook is broken")

    with pytest.raises(ChainBuildError, match="hook is broken"):
        factory.create("culinary").with_model(hook).invoke({"dish": "borscht"})


def test_hook_returning_non_runnable_is_a_build_error(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A hook that returns something other than a runnable fails the build.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})
    broken = chain.with_model(cast("Any", lambda model: None))

    with pytest.raises(ChainBuildError):
        broken.invoke({"dish": "borscht"})


def test_hooks_apply_in_order_and_survive_rebuild(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Hooks apply in the order they were added and again after a rebuild.
    """

    chain = (
        factory.create("culinary")
        .with_model(lambda m: m.bind(tool_names=["first"]))
        .with_model(lambda m: m | RunnableLambda(lambda message: str(message.content).upper()))
    )
    chain.invoke({"dish": "borscht"})

    client.version = 2
    client.config = {"model": "fake-2", "provider": "fake"}

    assert chain.invoke({"dish": "borscht"}) == "FAKE-2|NONE|INGREDIENTS OF BORSCHT|FIRST"


def test_copies_share_the_client_and_hooks_and_start_cold(
    factory: LangfuseChainFactory, client: FakeLangfuse, builds: list[PromptClient]
) -> None:
    """
    copy and deepcopy share the client and the hooks and build their own chain.
    """

    chain = factory.create("culinary").with_model(lambda m: m.bind(tool_names=["hooked"]))
    chain.invoke({"dish": "borscht"})

    deep = copy.deepcopy(chain)
    shallow = copy.copy(chain)

    assert deep._prompts._client is client
    assert deep.invoke({"dish": "borscht"}).content == "fake-1|0.1|Ingredients of borscht|hooked"
    assert shallow.invoke({"dish": "borscht"}).content == "fake-1|0.1|Ingredients of borscht|hooked"
    assert len(builds) == 3
    assert deep.get_name() == "culinary"


# Tracing


def test_prompt_is_attached_to_trace_metadata(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    The prompt is attached to the trace metadata once per call.
    """

    handler = RecordingHandler()

    factory.create("culinary").invoke({"dish": "borscht"}, config={"callbacks": [handler]})

    prompts = [m["langfuse_prompt"] for _, m in handler.chain_starts if "langfuse_prompt" in m]
    assert len(prompts) == 1
    assert prompts[0].name == "culinary"
    assert prompts[0].version == client.version


def test_trace_metadata_holds_a_copy_of_the_cached_prompt(
    factory: LangfuseChainFactory,
    client: FakeLangfuse,
    builds: list[PromptClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The trace metadata holds a copy, so mutating it does not change the SDK cache.
    """

    # The real SDK returns the same cached object on every call.
    cached = client.get_prompt("culinary")
    monkeypatch.setattr(client, "get_prompt", lambda name, **kwargs: cached)
    handler = RecordingHandler()
    chain = factory.create("culinary")

    chain.invoke({"dish": "borscht"}, config={"callbacks": [handler]})
    prompt = next(m["langfuse_prompt"] for _, m in handler.chain_starts if "langfuse_prompt" in m)
    assert prompt is not cached
    assert prompt == cached

    prompt.config["mutated"] = True
    chain.invoke({"dish": "borscht"})

    assert "mutated" not in cached.config
    assert len(builds) == 1


def test_default_run_name_is_prompt_name(factory: LangfuseChainFactory) -> None:
    """
    The run name defaults to the prompt name.
    """

    handler = RecordingHandler()
    chain = factory.create("culinary")

    chain.invoke({"dish": "borscht"}, config={"callbacks": [handler]})

    assert chain.get_name() == "culinary"
    assert handler.chain_starts[0][0] == "culinary"


def test_with_config_overrides_run_name(factory: LangfuseChainFactory) -> None:
    """
    with_config(run_name=...) overrides the default run name.
    """

    handler = RecordingHandler()
    chain = factory.create("culinary").with_config(run_name="custom")

    chain.invoke({"dish": "borscht"}, config={"callbacks": [handler]})

    assert handler.chain_starts[0][0] == "custom"


# Streaming


def test_stream(factory: LangfuseChainFactory) -> None:
    """
    stream yields the chunks of the model.
    """

    chunks = list(factory.create("culinary").stream({"dish": "borscht"}))

    assert "".join(str(c.content) for c in chunks) == "fake-1|0.1|Ingredients of borscht|"


async def test_astream(factory: LangfuseChainFactory) -> None:
    """
    astream yields the chunks of the model.
    """

    chunks = [c async for c in factory.create("culinary").astream({"dish": "borscht"})]

    assert "".join(str(c.content) for c in chunks) == "fake-1|0.1|Ingredients of borscht|"


def test_transform(factory: LangfuseChainFactory) -> None:
    """
    transform renders the input and streams the model output.
    """

    chunks = list(factory.create("culinary").transform(iter([{"dish": "borscht"}])))

    assert "".join(str(c.content) for c in chunks) == "fake-1|0.1|Ingredients of borscht|"


async def test_atransform(factory: LangfuseChainFactory) -> None:
    """
    atransform renders the input and streams the model output.
    """

    async def inputs() -> AsyncIterator[dict[str, Any]]:
        yield {"dish": "borscht"}

    chunks = [c async for c in factory.create("culinary").atransform(inputs())]

    assert "".join(str(c.content) for c in chunks) == "fake-1|0.1|Ingredients of borscht|"


def test_stream_is_lazy(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    stream fetches the prompt on the first chunk, not on the call.
    """

    client.error = ConnectionError("boom")
    chain = factory.create("culinary")

    iterator = chain.stream({"dish": "borscht"})

    with pytest.raises(PromptFetchError):
        next(iterator)


async def test_astream_events_exposes_prompt_and_model(factory: LangfuseChainFactory) -> None:
    """
    astream_events reports the prompt and the model events of the inner chain.
    """

    events = [e["event"] async for e in factory.create("culinary").astream_events({"dish": "borscht"}, version="v2")]

    assert "on_prompt_start" in events
    assert "on_chat_model_stream" in events


def test_batch_with_return_exceptions_returns_the_error_per_input(
    factory: LangfuseChainFactory, client: FakeLangfuse
) -> None:
    """
    The inherited batch returns the results in order and, with return_exceptions, the fetch error per input.
    """

    chain = factory.create("culinary")
    results = chain.batch([{"dish": "borscht"}, {"dish": "soup"}])

    client.error = ConnectionError("boom")
    errors = factory.create("culinary").batch([{"dish": "a"}, {"dish": "b"}], return_exceptions=True)

    assert [r.content for r in results] == ["fake-1|0.1|Ingredients of borscht|", "fake-1|0.1|Ingredients of soup|"]
    assert [type(e) for e in errors] == [PromptFetchError, PromptFetchError]
