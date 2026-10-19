"""
The runnable: rebuilding on prompt changes, failure handling, hooks, tracing and the Runnable interface.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import threading
import time

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

import pytest

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from pydantic import BaseModel

from langfuse_hotswap import ChainBuildError, LangfuseChainFactory, PromptFetchError

from .fakes import RecordingHandler

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langchain_core.language_models import BaseChatModel, LanguageModelInput
    from langchain_core.runnables import Runnable
    from langfuse.model import PromptClient

    from .fakes import FakeLangfuse


class Answer(BaseModel):
    """
    Structured output schema of the hook tests.
    """

    text: str


# Rebuilding


def test_same_version_reuses_chain(
    factory: LangfuseChainFactory, client: FakeLangfuse, init_calls: list[dict[str, Any]]
) -> None:
    """
    The same prompt is fetched on every call but the chain is built once.
    """

    chain = factory.create("culinary")

    chain.invoke({"dish": "borscht"})
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert len(init_calls) == 1
    assert len(client.calls) == 2


def test_new_version_rebuilds_chain(
    factory: LangfuseChainFactory, client: FakeLangfuse, init_calls: list[dict[str, Any]]
) -> None:
    """
    A new prompt version rebuilds the chain with the new template and model.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})

    client.version = 2
    client.messages = [("user", "Recipe of {{dish}}")]
    client.config = {"model": "fake-2", "model_provider": "fake", "temperature": 0.9}
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-2|0.9|Recipe of borscht|"
    assert len(init_calls) == 2


def test_same_version_number_with_new_content_rebuilds(
    factory: LangfuseChainFactory, client: FakeLangfuse, init_calls: list[dict[str, Any]]
) -> None:
    """
    A prompt with the same version number but a different config rebuilds the chain.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})

    client.config = {"model": "fake-2", "model_provider": "fake"}
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-2|None|Ingredients of borscht|"
    assert len(init_calls) == 2


def test_concurrent_cold_start_builds_once(factory: LangfuseChainFactory, init_calls: list[dict[str, Any]]) -> None:
    """
    Concurrent first calls from threads build the chain once.
    """

    chain = factory.create("culinary").with_model(lambda model: (time.sleep(0.05), model)[1])

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: chain.invoke({"dish": "borscht"}), range(8)))

    assert len(init_calls) == 1
    assert all(r.content == "fake-1|0.1|Ingredients of borscht|" for r in results)


def test_calls_during_a_rebuild_are_served_by_the_previous_chain(
    factory: LangfuseChainFactory, client: FakeLangfuse
) -> None:
    """
    A call that arrives while another thread rebuilds is served by the previous chain.
    """

    building = threading.Event()
    release = threading.Event()

    def hook(model: BaseChatModel) -> Runnable[LanguageModelInput, BaseMessage]:
        if client.version == 2:
            building.set()
            release.wait(5)
        return model

    chain = factory.create("culinary").with_model(hook)
    chain.invoke({"dish": "borscht"})
    client.version = 2
    client.config = {"model": "fake-2", "model_provider": "fake"}

    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(chain.invoke, {"dish": "borscht"})
        assert building.wait(5)
        meanwhile = chain.invoke({"dish": "borscht"})
        release.set()
        rebuilt = future.result(5)

    assert meanwhile.content == "fake-1|0.1|Ingredients of borscht|"
    assert rebuilt.content == "fake-2|None|Ingredients of borscht|"


# Build failures


def test_broken_new_version_keeps_last_working_chain_and_logs_once(
    factory: LangfuseChainFactory,
    client: FakeLangfuse,
    init_calls: list[dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    A version that fails to build is served by the previous chain and logged once.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})

    client.version = 2
    client.config = {"temperature": 0.9}
    with caplog.at_level(logging.ERROR, logger="langfuse_hotswap"):
        results = [chain.invoke({"dish": "borscht"}) for _ in range(3)]

    assert all(r.content == "fake-1|0.1|Ingredients of borscht|" for r in results)
    assert caplog.text.count("keeping version 1") == 1
    assert "version 2" in caplog.text
    assert len(init_calls) == 1


def test_broken_version_is_retried_after_a_minute(
    factory: LangfuseChainFactory,
    client: FakeLangfuse,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A version that fails to build is retried and logged again only after a minute.
    """

    now = [1000.0]
    monkeypatch.setattr("langfuse_hotswap._runnable.time.monotonic", lambda: now[0])
    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})
    client.version = 2
    client.config = {"model": "fake-2", "model_provider": "fake", "fail": True}

    with caplog.at_level(logging.ERROR, logger="langfuse_hotswap"):
        chain.invoke({"dish": "borscht"})
        now[0] += 30
        chain.invoke({"dish": "borscht"})
        assert caplog.text.count("keeping version 1") == 1
        now[0] += 31
        chain.invoke({"dish": "borscht"})
        assert caplog.text.count("keeping version 1") == 2

    client.config = {"model": "fake-2", "model_provider": "fake"}
    now[0] += 61
    assert chain.invoke({"dish": "borscht"}).content == "fake-2|None|Ingredients of borscht|"


def test_recreated_broken_version_is_retried(
    factory: LangfuseChainFactory, client: FakeLangfuse, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A broken version recreated with a fixed config under the same number is built.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})
    client.version = 2
    client.config = {}
    with caplog.at_level(logging.ERROR, logger="langfuse_hotswap"):
        chain.invoke({"dish": "borscht"})

    client.config = {"model": "fake-2", "model_provider": "fake"}
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-2|None|Ingredients of borscht|"


def test_fixed_version_after_broken_one_is_picked_up(
    factory: LangfuseChainFactory, client: FakeLangfuse, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A new version after a broken one is built right away.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})
    client.version = 2
    client.config = {}
    with caplog.at_level(logging.ERROR, logger="langfuse_hotswap"):
        chain.invoke({"dish": "borscht"})

    client.version = 3
    client.config = {"model": "fake-3", "model_provider": "fake"}
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-3|None|Ingredients of borscht|"


def test_broken_version_without_previous_chain_raises(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Without a previous chain a build failure raises ChainBuildError.
    """

    client.config = {}

    with pytest.raises(ChainBuildError):
        factory.create("culinary").invoke({"dish": "borscht"})


def test_broken_cold_start_raises_the_cached_error_for_a_minute(
    factory: LangfuseChainFactory,
    client: FakeLangfuse,
    init_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Without a previous chain a failed build raises the same error without rebuilding for a minute.
    """

    now = [1000.0]
    monkeypatch.setattr("langfuse_hotswap._runnable.time.monotonic", lambda: now[0])
    client.config = {"model": "fake-1", "model_provider": "fake", "fail": True}
    chain = factory.create("culinary")

    with pytest.raises(ChainBuildError, match="provider is down") as first:
        chain.invoke({"dish": "borscht"})
    with pytest.raises(ChainBuildError, match="provider is down") as second:
        chain.invoke({"dish": "borscht"})
    assert len(init_calls) == 1
    assert second.value is not first.value
    assert second.value.__cause__ is first.value

    now[0] += 61
    with pytest.raises(ChainBuildError, match="provider is down"):
        chain.invoke({"dish": "borscht"})
    assert len(init_calls) == 2

    client.config = {"model": "fake-2", "model_provider": "fake"}
    assert chain.invoke({"dish": "borscht"}).content == "fake-2|None|Ingredients of borscht|"


def test_concurrent_broken_cold_start_builds_once(
    factory: LangfuseChainFactory, client: FakeLangfuse, init_calls: list[dict[str, Any]]
) -> None:
    """
    Concurrent first calls on a broken prompt build once and all raise ChainBuildError.
    """

    client.config = {"model": "fake-1", "model_provider": "fake", "fail": True}
    chain = factory.create("culinary").with_model(lambda model: (time.sleep(0.05), model)[1])

    def call(_: int) -> Exception | None:
        try:
            chain.invoke({"dish": "borscht"})
        except ChainBuildError as exc:
            return exc
        return None

    with ThreadPoolExecutor(8) as pool:
        errors = list(pool.map(call, range(8)))

    assert all(isinstance(e, ChainBuildError) for e in errors)
    assert len(init_calls) == 1


# Prompt fetching


def test_fetch_error_is_wrapped(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A fetch failure becomes PromptFetchError with the original as the cause.
    """

    client.error = ConnectionError("boom")

    with pytest.raises(PromptFetchError, match="'culinary'") as info:
        factory.create("culinary").invoke({"dish": "borscht"})

    assert info.value.__cause__ is client.error


def test_fetch_error_works_with_fallbacks(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    PromptFetchError is handled by with_fallbacks in invoke and stream.
    """

    client.error = ConnectionError("boom")
    fallback = RunnableLambda(lambda _: AIMessage("fallback"))
    chain = factory.create("culinary").with_fallbacks([fallback], exceptions_to_handle=(PromptFetchError,))

    assert chain.invoke({"dish": "borscht"}).content == "fallback"
    assert [c.content for c in chain.stream({"dish": "borscht"})] == ["fallback"]


def test_fetch_error_keeps_last_working_chain_and_logs_once_a_minute(
    factory: LangfuseChainFactory,
    client: FakeLangfuse,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A fetch failure is served by the previous chain and logged at most once a minute.
    """

    now = [1000.0]
    monkeypatch.setattr("langfuse_hotswap._runnable.time.monotonic", lambda: now[0])
    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})
    client.error = ConnectionError("boom")

    with caplog.at_level(logging.ERROR, logger="langfuse_hotswap"):
        results = [chain.invoke({"dish": "borscht"}) for _ in range(3)]
        now[0] += 61
        results.append(chain.invoke({"dish": "borscht"}))

    assert all(r.content == "fake-1|0.1|Ingredients of borscht|" for r in results)
    assert caplog.text.count("keeping version 1") == 2

    client.error = None
    client.version = 2
    client.config = {"model": "fake-2", "model_provider": "fake"}
    assert chain.invoke({"dish": "borscht"}).content == "fake-2|None|Ingredients of borscht|"


def test_cache_ttl_is_passed_to_get_prompt(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    The name, the label and cache_ttl_seconds reach get_prompt.
    """

    factory.create("culinary", label="latest", cache_ttl_seconds=300).invoke({"dish": "borscht"})

    assert client.calls[0]["name"] == "culinary"
    assert client.calls[0]["label"] == "latest"
    assert client.calls[0]["cache_ttl_seconds"] == 300


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


def test_with_model_hook_can_read_the_prompt(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    A hook with a prompt parameter, positional or keyword-only, receives the prompt with the full config.
    """

    factory = LangfuseChainFactory(cast("Any", client), allowed_config_keys={"model", "model_provider"})
    client.config = {"model": "fake-1", "model_provider": "fake", "tools": ["search", "code"]}

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
    client.config = {"model": "fake-2", "model_provider": "fake"}

    assert chain.invoke({"dish": "borscht"}) == "FAKE-2|NONE|INGREDIENTS OF BORSCHT|FIRST"


def test_copies_share_the_client_and_hooks_and_start_cold(
    factory: LangfuseChainFactory, client: FakeLangfuse, init_calls: list[dict[str, Any]]
) -> None:
    """
    copy and deepcopy share the client and the hooks and build their own chain.
    """

    chain = factory.create("culinary").with_model(lambda m: m.bind(tool_names=["hooked"]))
    chain.invoke({"dish": "borscht"})

    deep = copy.deepcopy(chain)
    shallow = copy.copy(chain)

    assert deep._client is client
    assert deep.invoke({"dish": "borscht"}).content == "fake-1|0.1|Ingredients of borscht|hooked"
    assert shallow.invoke({"dish": "borscht"}).content == "fake-1|0.1|Ingredients of borscht|hooked"
    assert len(init_calls) == 3
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
    init_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The real SDK returns the same cached object on every call.
    """
    The trace metadata holds a copy, so mutating it does not change the SDK cache.
    """

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
    assert len(init_calls) == 1


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


# Async


async def test_ainvoke_resolves_the_chain_off_the_event_loop(
    factory: LangfuseChainFactory, client: FakeLangfuse, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The first ainvoke fetches the prompt in the executor.
    """

    threads: list[int] = []
    original = client.get_prompt

    def get_prompt(name: str, **kwargs: Any) -> PromptClient:
        threads.append(threading.get_ident())
        return original(name, **kwargs)

    monkeypatch.setattr(client, "get_prompt", get_prompt)
    result = await factory.create("culinary").ainvoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert threads == [threads[0]]
    assert threads[0] != threading.get_ident()


async def test_warm_ainvoke_fetches_on_the_event_loop_and_rebuilds_off_it(
    factory: LangfuseChainFactory, client: FakeLangfuse, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    With a warm cache ainvoke fetches on the event loop and rebuilds in the executor.
    """

    fetch_threads: list[int] = []
    build_threads: list[int] = []
    original = client.get_prompt

    def get_prompt(name: str, **kwargs: Any) -> PromptClient:
        fetch_threads.append(threading.get_ident())
        return original(name, **kwargs)

    def hook(model: BaseChatModel) -> Runnable[LanguageModelInput, BaseMessage]:
        build_threads.append(threading.get_ident())
        return model

    monkeypatch.setattr(client, "get_prompt", get_prompt)
    chain = factory.create("culinary").with_model(hook)
    loop_thread = threading.get_ident()

    await chain.ainvoke({"dish": "borscht"})
    await chain.ainvoke({"dish": "borscht"})
    client.version = 2
    result = await chain.ainvoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert [t == loop_thread for t in fetch_threads] == [False, True, True]
    assert loop_thread not in build_threads
    assert len(build_threads) == 2


@pytest.mark.parametrize("failing", [True, False])
async def test_ainvoke_fetches_in_the_executor_after_a_failure_or_without_cache(
    client: FakeLangfuse, init_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch, failing: bool
) -> None:
    """
    After a failed fetch or with cache_ttl_seconds=0 ainvoke fetches in the executor.
    """

    threads: list[int] = []
    original = client.get_prompt

    def get_prompt(name: str, **kwargs: Any) -> PromptClient:
        threads.append(threading.get_ident())
        return original(name, **kwargs)

    monkeypatch.setattr(client, "get_prompt", get_prompt)
    factory = LangfuseChainFactory(cast("Any", client), allowed_config_keys=None)
    chain = factory.create("culinary", cache_ttl_seconds=None if failing else 0)
    await chain.ainvoke({"dish": "borscht"})
    if failing:
        client.error = ConnectionError("boom")
        await chain.ainvoke({"dish": "borscht"})
    threads.clear()

    result = await chain.ainvoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert threading.get_ident() not in threads


async def test_concurrent_async_cold_start_builds_once(
    factory: LangfuseChainFactory, init_calls: list[dict[str, Any]]
) -> None:
    """
    Concurrent first ainvoke calls build the chain once.
    """

    chain = factory.create("culinary").with_model(lambda model: (time.sleep(0.05), model)[1])

    results = await asyncio.gather(*(chain.ainvoke({"dish": "borscht"}) for _ in range(8)))

    assert len(init_calls) == 1
    assert all(r.content == "fake-1|0.1|Ingredients of borscht|" for r in results)


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


# Batching


async def test_empty_batches_do_not_fetch_the_prompt(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Every batch method returns an empty result for empty inputs without fetching the prompt.
    """

    client.error = ConnectionError("boom")
    chain = factory.create("culinary")

    assert chain.batch([]) == []
    assert await chain.abatch([]) == []
    assert list(chain.batch_as_completed([])) == []
    assert [item async for item in chain.abatch_as_completed([])] == []
    assert client.calls == []


def test_batch_fetches_the_prompt_once(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    batch fetches the prompt once for all inputs.
    """

    results = factory.create("culinary").batch([{"dish": "borscht"}, {"dish": "soup"}])

    assert [r.content for r in results] == ["fake-1|0.1|Ingredients of borscht|", "fake-1|0.1|Ingredients of soup|"]
    assert len(client.calls) == 1


def test_batch_with_return_exceptions_returns_fetch_error(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    batch with return_exceptions returns the fetch error for every input.
    """

    client.error = ConnectionError("boom")

    results = factory.create("culinary").batch([{"dish": "a"}, {"dish": "b"}], return_exceptions=True)

    assert [type(r) for r in results] == [PromptFetchError, PromptFetchError]


async def test_abatch_with_return_exceptions(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    abatch fetches the prompt once and passes the config to the chain.
    """

    results = await factory.create("culinary").abatch(
        [{"dish": "borscht"}, {"dish": "soup"}], config={"max_concurrency": 2}, return_exceptions=True
    )

    assert [r.content for r in results] == ["fake-1|0.1|Ingredients of borscht|", "fake-1|0.1|Ingredients of soup|"]
    assert len(client.calls) == 1


async def test_abatch_with_return_exceptions_returns_build_error(
    factory: LangfuseChainFactory, client: FakeLangfuse
) -> None:
    """
    abatch with return_exceptions returns the build error for every input.
    """

    client.config = {}

    results = await factory.create("culinary").abatch([{"dish": "a"}], return_exceptions=True)

    assert type(results[0]) is ChainBuildError


def test_batch_as_completed_fetches_once_and_returns_errors(
    factory: LangfuseChainFactory, client: FakeLangfuse
) -> None:
    """
    batch_as_completed fetches once and returns or raises the fetch error.
    """

    results = dict(factory.create("culinary").batch_as_completed([{"dish": "a"}, {"dish": "b"}]))
    assert {i: r.content for i, r in results.items()} == {
        0: "fake-1|0.1|Ingredients of a|",
        1: "fake-1|0.1|Ingredients of b|",
    }
    assert len(client.calls) == 1

    client.error = ConnectionError("boom")
    errors = list(factory.create("culinary").batch_as_completed([{"dish": "a"}], return_exceptions=True))
    assert [(i, type(e)) for i, e in errors] == [(0, PromptFetchError)]
    with pytest.raises(PromptFetchError):
        list(factory.create("culinary").batch_as_completed([{"dish": "a"}]))


async def test_abatch_as_completed_fetches_once_and_returns_errors(
    factory: LangfuseChainFactory, client: FakeLangfuse
) -> None:
    """
    abatch_as_completed fetches once and returns the build error.
    """

    chain = factory.create("culinary")
    results = {i: r async for i, r in chain.abatch_as_completed([{"dish": "a"}, {"dish": "b"}])}
    assert {i: r.content for i, r in results.items()} == {
        0: "fake-1|0.1|Ingredients of a|",
        1: "fake-1|0.1|Ingredients of b|",
    }
    assert len(client.calls) == 1

    client.config = {}
    cold = factory.create("culinary")
    errors = [(i, e) async for i, e in cold.abatch_as_completed([{"dish": "a"}], return_exceptions=True)]
    assert [(i, type(e)) for i, e in errors] == [(0, ChainBuildError)]
