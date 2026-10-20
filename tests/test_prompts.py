"""
The prompt manager: rebuilding on prompt changes, build and fetch failures, the async path.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

import pytest

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from langfuse_hotswap import ChainBuildError, PromptFetchError, PromptManager

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel, LanguageModelInput
    from langchain_core.messages import BaseMessage
    from langchain_core.runnables import Runnable
    from langfuse.model import PromptClient

    from langfuse_hotswap import LangfuseChainFactory

    from .fakes import FakeLangfuse


def slow(model: BaseChatModel) -> Runnable[LanguageModelInput, BaseMessage]:
    """
    Hook that makes a build slow enough for concurrent calls to overlap.
    """

    time.sleep(0.05)
    return model


# Rebuilding


def test_same_version_reuses_chain(
    factory: LangfuseChainFactory, client: FakeLangfuse, builds: list[PromptClient]
) -> None:
    """
    The same prompt is fetched on every call but the chain is built once.
    """

    chain = factory.create("culinary")

    chain.invoke({"dish": "borscht"})
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert len(builds) == 1
    assert len(client.calls) == 2


def test_new_version_rebuilds_chain(
    factory: LangfuseChainFactory, client: FakeLangfuse, builds: list[PromptClient]
) -> None:
    """
    A new prompt version rebuilds the chain with the new template and model.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})

    client.version = 2
    client.messages = [("user", "Recipe of {{dish}}")]
    client.config = {"model": "fake-2", "provider": "fake", "temperature": 0.9}
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-2|0.9|Recipe of borscht|"
    assert len(builds) == 2


def test_same_version_number_with_new_content_rebuilds(
    factory: LangfuseChainFactory, client: FakeLangfuse, builds: list[PromptClient]
) -> None:
    """
    A prompt with the same version number but a different config rebuilds the chain.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})

    client.config = {"model": "fake-2", "provider": "fake"}
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-2|None|Ingredients of borscht|"
    assert len(builds) == 2


def test_concurrent_cold_start_builds_once(factory: LangfuseChainFactory, builds: list[PromptClient]) -> None:
    """
    Concurrent first calls from threads build the chain once.
    """

    chain = factory.create("culinary").with_model(slow)

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: chain.invoke({"dish": "borscht"}), range(8)))

    assert len(builds) == 1
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
    client.config = {"model": "fake-2", "provider": "fake"}

    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(chain.invoke, {"dish": "borscht"})
        assert building.wait(5)
        meanwhile = chain.invoke({"dish": "borscht"})
        release.set()
        rebuilt = future.result(5)

    assert meanwhile.content == "fake-1|0.1|Ingredients of borscht|"
    assert rebuilt.content == "fake-2|None|Ingredients of borscht|"


def test_created_runnables_are_independent(factory: LangfuseChainFactory, builds: list[PromptClient]) -> None:
    """
    Runnables created by one factory build their own chains.
    """

    first = factory.create("culinary")
    second = factory.create("culinary")

    first.invoke({"dish": "borscht"})
    first.invoke({"dish": "borscht"})
    second.invoke({"dish": "borscht"})

    assert len(builds) == 2


# Build failures


def test_broken_new_version_keeps_last_working_chain_and_logs_once(
    factory: LangfuseChainFactory,
    client: FakeLangfuse,
    builds: list[PromptClient],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    A version that fails to build is served by the previous chain and logged once.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})

    client.version = 2
    client.config = {"temperature": "hot"}
    with caplog.at_level(logging.ERROR, logger="langfuse_hotswap"):
        results = [chain.invoke({"dish": "borscht"}) for _ in range(3)]

    assert all(r.content == "fake-1|0.1|Ingredients of borscht|" for r in results)
    assert caplog.text.count("keeping version 1") == 1
    assert "version 2" in caplog.text
    assert len(builds) == 2


def test_recreated_broken_version_is_retried(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A broken version recreated with a fixed config under the same number is built.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})
    client.version = 2
    client.config = {"temperature": "hot"}
    chain.invoke({"dish": "borscht"})

    client.config = {"model": "fake-2", "provider": "fake"}
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-2|None|Ingredients of borscht|"


def test_fixed_version_after_broken_one_is_picked_up(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A new version after a broken one is built right away.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})
    client.version = 2
    client.config = {"temperature": "hot"}
    chain.invoke({"dish": "borscht"})

    client.version = 3
    client.config = {"model": "fake-3", "provider": "fake"}
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-3|None|Ingredients of borscht|"


def test_broken_version_without_previous_chain_raises(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Without a previous chain a build failure raises ChainBuildError with the original as the cause.
    """

    client.config = {"temperature": "hot"}

    with pytest.raises(ChainBuildError, match="temperature") as info:
        factory.create("culinary").invoke({"dish": "borscht"})

    assert type(info.value.__cause__).__name__ == "ValidationError"


def test_broken_cold_start_raises_the_cached_error_until_the_prompt_changes(
    factory: LangfuseChainFactory, client: FakeLangfuse, builds: list[PromptClient]
) -> None:
    """
    Without a previous chain a failed build raises the same error without rebuilding until the prompt changes.
    """

    client.config = {"model": "fake-1", "provider": "fake", "temperature": "hot"}
    chain = factory.create("culinary")

    with pytest.raises(ChainBuildError, match="temperature") as first:
        chain.invoke({"dish": "borscht"})
    with pytest.raises(ChainBuildError, match="temperature") as second:
        chain.invoke({"dish": "borscht"})
    assert len(builds) == 1
    assert second.value is not first.value
    assert second.value.__cause__ is first.value

    client.config = {"model": "fake-2", "provider": "fake"}
    assert chain.invoke({"dish": "borscht"}).content == "fake-2|None|Ingredients of borscht|"
    assert len(builds) == 2


def test_concurrent_broken_cold_start_builds_once(
    factory: LangfuseChainFactory, client: FakeLangfuse, builds: list[PromptClient]
) -> None:
    """
    Concurrent first calls on a broken prompt build once and all raise ChainBuildError.
    """

    client.config = {"model": "fake-1", "provider": "fake", "temperature": "hot"}
    chain = factory.create("culinary").with_model(slow)

    def call(_: int) -> Exception | None:
        try:
            chain.invoke({"dish": "borscht"})
        except ChainBuildError as exc:
            return exc
        return None

    with ThreadPoolExecutor(8) as pool:
        errors = list(pool.map(call, range(8)))

    assert all(isinstance(e, ChainBuildError) for e in errors)
    assert len(builds) == 1


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


def test_fetch_error_keeps_last_working_chain_and_logs_once_per_outage(
    factory: LangfuseChainFactory, client: FakeLangfuse, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A fetch failure is served by the previous chain and logged once until a fetch succeeds again.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})
    client.error = ConnectionError("boom")

    with caplog.at_level(logging.ERROR, logger="langfuse_hotswap"):
        results = [chain.invoke({"dish": "borscht"}) for _ in range(3)]
        client.error = None
        chain.invoke({"dish": "borscht"})
        client.error = ConnectionError("boom again")
        chain.invoke({"dish": "borscht"})

    assert all(r.content == "fake-1|0.1|Ingredients of borscht|" for r in results)
    assert caplog.text.count("keeping version 1") == 2

    client.error = None
    client.version = 2
    client.config = {"model": "fake-2", "provider": "fake"}
    assert chain.invoke({"dish": "borscht"}).content == "fake-2|None|Ingredients of borscht|"


def test_cold_start_fetches_one_at_a_time(
    factory: LangfuseChainFactory, client: FakeLangfuse, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Concurrent calls without a built chain fetch the prompt one after another, so the SDK fetches once.
    """

    started: list[int] = []
    release = threading.Event()
    original = client.get_prompt

    def get_prompt(name: str, **kwargs: Any) -> PromptClient:
        started.append(threading.get_ident())
        release.wait(5)
        return original(name, **kwargs)

    monkeypatch.setattr(client, "get_prompt", get_prompt)
    chain = factory.create("culinary")

    with ThreadPoolExecutor(4) as pool:
        futures = [pool.submit(chain.invoke, {"dish": "borscht"}) for _ in range(4)]
        time.sleep(0.1)
        in_flight = len(started)
        release.set()
        results = [f.result(5) for f in futures]

    assert in_flight == 1
    assert all(r.content == "fake-1|0.1|Ingredients of borscht|" for r in results)


def test_a_built_value_of_none_is_cached(client: FakeLangfuse) -> None:
    """
    A build that returns None is kept as the current value and not repeated.
    """

    manager: PromptManager[None] = PromptManager(cast("Any", client), "culinary", {})
    builds: list[PromptClient] = []

    def build(prompt: PromptClient) -> None:
        builds.append(prompt)

    manager.resolve(build)
    manager.resolve(build)

    assert len(builds) == 1


def test_cache_ttl_is_passed_to_get_prompt(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    The name, the label and cache_ttl_seconds reach get_prompt.
    """

    factory.create("culinary", label="latest", cache_ttl_seconds=300).invoke({"dish": "borscht"})

    assert client.calls[0]["name"] == "culinary"
    assert client.calls[0]["label"] == "latest"
    assert client.calls[0]["cache_ttl_seconds"] == 300


# Async


async def test_ainvoke_resolves_the_chain_off_the_event_loop(
    factory: LangfuseChainFactory, client: FakeLangfuse
) -> None:
    """
    The first ainvoke fetches the prompt in the executor.
    """

    result = await factory.create("culinary").ainvoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert client.threads == [client.threads[0]]
    assert client.threads[0] != threading.get_ident()


async def test_warm_ainvoke_fetches_on_the_event_loop_and_rebuilds_off_it(
    factory: LangfuseChainFactory, client: FakeLangfuse
) -> None:
    """
    With a warm cache ainvoke fetches on the event loop and rebuilds in the executor.
    """

    build_threads: list[int] = []

    def hook(model: BaseChatModel) -> Runnable[LanguageModelInput, BaseMessage]:
        build_threads.append(threading.get_ident())
        return model

    chain = factory.create("culinary").with_model(hook)
    loop_thread = threading.get_ident()

    await chain.ainvoke({"dish": "borscht"})
    await chain.ainvoke({"dish": "borscht"})
    client.version = 2
    result = await chain.ainvoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert [t == loop_thread for t in client.threads] == [False, True, True]
    assert loop_thread not in build_threads
    assert len(build_threads) == 2


@pytest.mark.parametrize("failing", [True, False])
async def test_ainvoke_fetches_in_the_executor_after_a_failure_or_without_cache(
    factory: LangfuseChainFactory, client: FakeLangfuse, failing: bool
) -> None:
    """
    After a failed fetch or with cache_ttl_seconds=0 ainvoke fetches in the executor.
    """

    chain = factory.create("culinary", cache_ttl_seconds=None if failing else 0)
    await chain.ainvoke({"dish": "borscht"})
    if failing:
        client.error = ConnectionError("boom")
        await chain.ainvoke({"dish": "borscht"})
    client.threads.clear()

    result = await chain.ainvoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert threading.get_ident() not in client.threads


async def test_prompt_without_is_fallback_is_fetched_in_the_executor(
    factory: LangfuseChainFactory, client: FakeLangfuse, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A prompt without the SDK ``is_fallback`` attribute is fetched in the executor on every ainvoke.
    """

    original = client.get_prompt

    def get_prompt(name: str, **kwargs: Any) -> PromptClient:
        prompt = original(name, **kwargs)
        del prompt.is_fallback
        return prompt

    monkeypatch.setattr(client, "get_prompt", get_prompt)
    chain = factory.create("culinary")
    await chain.ainvoke({"dish": "borscht"})

    result = await chain.ainvoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert threading.get_ident() not in client.threads


async def test_concurrent_async_cold_start_builds_once(
    factory: LangfuseChainFactory, builds: list[PromptClient]
) -> None:
    """
    Concurrent first ainvoke calls build the chain once.
    """

    chain = factory.create("culinary").with_model(slow)

    results = await asyncio.gather(*(chain.ainvoke({"dish": "borscht"}) for _ in range(8)))

    assert len(builds) == 1
    assert all(r.content == "fake-1|0.1|Ingredients of borscht|" for r in results)
