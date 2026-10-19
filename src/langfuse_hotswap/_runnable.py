"""
Runnable that rebuilds ``prompt | model`` when the Langfuse prompt changes.
"""

from __future__ import annotations

import copy
import inspect
import logging
import threading
import time

from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast, overload

from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.runnables.config import run_in_executor
from typing_extensions import TypeVar

from langfuse_hotswap._config import build_model_params
from langfuse_hotswap._errors import ChainBuildError, HotswapError, PromptFetchError
from langfuse_hotswap._template import LangfusePromptTemplate

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence

    from langchain_core.language_models import LanguageModelInput
    from langchain_core.tools import BaseTool
    from langchain_core.utils.pydantic import TypeBaseModel
    from langfuse import Langfuse
    from langfuse.model import PromptClient
    from pydantic import BaseModel

Output = TypeVar("Output", default=BaseMessage)
Schema = TypeVar("Schema", bound="BaseModel")


logger = logging.getLogger(__name__)


class _Built(NamedTuple):
    """
    A built chain and the prompt it was built from.
    """

    prompt: PromptClient
    chain: Runnable[dict[str, Any], Any]


class _Failure(NamedTuple):
    """
    A prompt that failed to build, the time of the attempt and the error.
    """

    prompt: PromptClient
    at: float
    error: ChainBuildError


class LangfusePromptRunnable(Runnable[dict[str, Any], Output]):
    """
    Renders a Langfuse prompt and runs it through a chat model built from the prompt config.

    Every call fetches the prompt through the SDK cache and delegates to ``template | model`` built
    for it. The chain is rebuilt when the prompt changes. A prompt that fails to build is retried at
    most once a minute, and the previous chain serves the calls meanwhile.
    """

    def __init__(
        self,
        client: Langfuse,
        prompt_name: str,
        *,
        prompt_kwargs: Mapping[str, Any],
        model_kwargs: Mapping[str, Any],
        provider_kwargs: Mapping[str, Mapping[str, Any]],
        allowed_config_keys: frozenset[str] | None,
    ) -> None:
        """
        ``prompt_kwargs`` are passed to ``client.get_prompt``, the rest to ``build_model_params``.
        """

        self.name = prompt_name
        self._client = client
        self._prompt_name = prompt_name
        self._prompt_kwargs = prompt_kwargs
        self._model_kwargs = model_kwargs
        self._provider_kwargs = provider_kwargs
        self._allowed_config_keys = allowed_config_keys
        self._hooks: tuple[tuple[Callable[..., Runnable[LanguageModelInput, Any]], bool], ...] = ()

        self._lock = threading.Lock()
        self._built: _Built | None = None
        self._failed: _Failure | None = None
        self._fetch_failed_at: float | None = None

    # Model customization: every method returns a copy, the hooks are applied at build time.

    def with_model(self, hook: Callable[..., Runnable[LanguageModelInput, Any]]) -> LangfusePromptRunnable[Any]:
        """
        Returns a copy whose model is replaced by ``hook(model)``.

        A hook with a ``prompt`` parameter is called as ``hook(model, prompt=prompt)`` with a copy of
        the Langfuse prompt client.
        """

        clone = self._clone()
        clone._hooks = (*self._hooks, (hook, _accepts_prompt(hook)))
        return clone

    @overload
    def with_structured_output(self, schema: type[Schema], **kwargs: Any) -> LangfusePromptRunnable[Schema]: ...

    @overload
    def with_structured_output(
        self, schema: dict[str, Any] | type, **kwargs: Any
    ) -> LangfusePromptRunnable[dict[str, Any]]: ...

    def with_structured_output(self, schema: Any, **kwargs: Any) -> LangfusePromptRunnable[Any]:
        """
        Returns a copy whose model output is parsed into ``schema`` by ``model.with_structured_output``.
        """

        return self.with_model(lambda model: model.with_structured_output(schema, **kwargs))

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        **kwargs: Any,
    ) -> LangfusePromptRunnable[BaseMessage]:
        """
        Returns a copy whose model has ``tools`` bound by ``model.bind_tools``.
        """

        return self.with_model(lambda model: model.bind_tools(tools, **kwargs))

    # Runnable interface: resolve the chain for the current prompt and delegate to it.

    def invoke(self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any) -> Output:
        return self._prepare().invoke(input, config, **kwargs)

    async def ainvoke(self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any) -> Output:
        chain = await self._aprepare(config)
        return await chain.ainvoke(input, config, **kwargs)

    def batch(
        self,
        inputs: list[dict[str, Any]],
        config: RunnableConfig | list[RunnableConfig] | None = None,
        *,
        return_exceptions: bool = False,
        **kwargs: Any,
    ) -> list[Output]:
        if not inputs:
            return []

        try:
            chain = self._prepare()
        except HotswapError as exc:
            if not return_exceptions:
                raise
            return cast("list[Output]", [exc] * len(inputs))

        return chain.batch(inputs, config, return_exceptions=return_exceptions, **kwargs)

    async def abatch(
        self,
        inputs: list[dict[str, Any]],
        config: RunnableConfig | list[RunnableConfig] | None = None,
        *,
        return_exceptions: bool = False,
        **kwargs: Any,
    ) -> list[Output]:
        if not inputs:
            return []

        try:
            chain = await self._aprepare(config if isinstance(config, dict) else None)
        except HotswapError as exc:
            if not return_exceptions:
                raise
            return cast("list[Output]", [exc] * len(inputs))

        return await chain.abatch(inputs, config, return_exceptions=return_exceptions, **kwargs)

    @overload
    def batch_as_completed(
        self,
        inputs: Sequence[dict[str, Any]],
        config: RunnableConfig | Sequence[RunnableConfig] | None = None,
        *,
        return_exceptions: Literal[False] = False,
        **kwargs: Any,
    ) -> Iterator[tuple[int, Output]]: ...

    @overload
    def batch_as_completed(
        self,
        inputs: Sequence[dict[str, Any]],
        config: RunnableConfig | Sequence[RunnableConfig] | None = None,
        *,
        return_exceptions: Literal[True],
        **kwargs: Any,
    ) -> Iterator[tuple[int, Output | Exception]]: ...

    def batch_as_completed(
        self,
        inputs: Sequence[dict[str, Any]],
        config: RunnableConfig | Sequence[RunnableConfig] | None = None,
        *,
        return_exceptions: bool = False,
        **kwargs: Any,
    ) -> Iterator[tuple[int, Output | Exception]]:
        if not inputs:
            return

        try:
            chain = self._prepare()
        except HotswapError as exc:
            if not return_exceptions:
                raise
            yield from ((index, exc) for index in range(len(inputs)))
            return

        yield from chain.batch_as_completed(inputs, config, return_exceptions=return_exceptions, **kwargs)

    @overload
    def abatch_as_completed(
        self,
        inputs: Sequence[dict[str, Any]],
        config: RunnableConfig | Sequence[RunnableConfig] | None = None,
        *,
        return_exceptions: Literal[False] = False,
        **kwargs: Any,
    ) -> AsyncIterator[tuple[int, Output]]: ...

    @overload
    def abatch_as_completed(
        self,
        inputs: Sequence[dict[str, Any]],
        config: RunnableConfig | Sequence[RunnableConfig] | None = None,
        *,
        return_exceptions: Literal[True],
        **kwargs: Any,
    ) -> AsyncIterator[tuple[int, Output | Exception]]: ...

    async def abatch_as_completed(
        self,
        inputs: Sequence[dict[str, Any]],
        config: RunnableConfig | Sequence[RunnableConfig] | None = None,
        *,
        return_exceptions: bool = False,
        **kwargs: Any,
    ) -> AsyncIterator[tuple[int, Output | Exception]]:
        if not inputs:
            return

        try:
            chain = await self._aprepare(cast("RunnableConfig", config) if isinstance(config, dict) else None)
        except HotswapError as exc:
            if not return_exceptions:
                raise
            for index in range(len(inputs)):
                yield index, exc
            return

        async for item in chain.abatch_as_completed(inputs, config, return_exceptions=return_exceptions, **kwargs):
            yield item

    def stream(self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any) -> Iterator[Output]:
        yield from self._prepare().stream(input, config, **kwargs)

    async def astream(
        self, input: dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any
    ) -> AsyncIterator[Output]:
        chain = await self._aprepare(config)
        async for chunk in chain.astream(input, config, **kwargs):
            yield chunk

    def get_input_schema(self, config: RunnableConfig | None = None) -> TypeBaseModel:
        """
        Returns the input schema of the current chain, or a permissive one if the chain cannot be built.
        """

        try:
            return self._prepare().get_input_schema(config)
        except HotswapError:
            return super().get_input_schema(config)

    def get_output_schema(self, config: RunnableConfig | None = None) -> TypeBaseModel:
        """
        Returns the output schema of the current chain, or a permissive one if the chain cannot be built.
        """

        try:
            return self._prepare().get_output_schema(config)
        except HotswapError:
            return super().get_output_schema(config)

    def __copy__(self) -> LangfusePromptRunnable[Output]:
        """
        Returns a copy that shares the client and the hooks and starts with an empty cache.
        """

        return self._clone()

    def __deepcopy__(self, memo: dict[int, Any]) -> LangfusePromptRunnable[Output]:
        """
        Returns a copy that shares the client and the hooks and starts with an empty cache.
        """

        return self._clone()

    # Chain lifecycle.

    def _clone(self) -> LangfusePromptRunnable[Any]:
        """
        Returns a copy with the same settings and hooks, its own lock and an empty cache.
        """

        clone: LangfusePromptRunnable[Any] = LangfusePromptRunnable(
            self._client,
            self._prompt_name,
            prompt_kwargs=self._prompt_kwargs,
            model_kwargs=self._model_kwargs,
            provider_kwargs=self._provider_kwargs,
            allowed_config_keys=self._allowed_config_keys,
        )
        clone._hooks = self._hooks
        return clone

    def _prepare(self) -> Runnable[dict[str, Any], Output]:
        """
        Returns the chain for the current prompt, building it if the prompt changed.
        """

        try:
            prompt = self._fetch()
        except PromptFetchError as exc:
            return self._serve_previous(exc)

        self._fetch_failed_at = None
        chain = self._current(prompt)
        if chain is None:
            chain = self._rebuild(prompt)
        return chain

    async def _aprepare(self, config: RunnableConfig | None) -> Runnable[dict[str, Any], Output]:
        """
        Async ``_prepare``: fetches on the event loop when the SDK cache is warm, otherwise in the executor.
        """

        if not self._cache_is_warm():
            return await run_in_executor(config, self._prepare)

        try:
            prompt = self._fetch()
        except PromptFetchError as exc:
            return self._serve_previous(exc)

        chain = self._current(prompt)
        if chain is None:
            chain = await run_in_executor(config, self._rebuild, prompt)
        return chain

    def _cache_is_warm(self) -> bool:
        """
        Returns whether ``get_prompt`` answers from the SDK cache without an HTTP request.
        """

        built = self._built
        # A prompt without the SDK ``is_fallback`` attribute is treated as a fallback.
        return (
            built is not None
            and not getattr(built.prompt, "is_fallback", True)
            and self._prompt_kwargs.get("cache_ttl_seconds") != 0
            and self._fetch_failed_at is None
        )

    def _fetch(self) -> PromptClient:
        """
        Fetches the prompt and wraps any failure into ``PromptFetchError``.
        """

        try:
            return self._client.get_prompt(self._prompt_name, **self._prompt_kwargs)
        except Exception as exc:
            label = self._prompt_kwargs.get("label")
            version = self._prompt_kwargs.get("version")
            raise PromptFetchError(
                f"Failed to fetch Langfuse prompt {self._prompt_name!r} (label={label!r}, version={version!r}): {exc}"
            ) from exc

    def _serve_previous(self, error: PromptFetchError) -> Runnable[dict[str, Any], Output]:
        """
        Returns the built chain after a failed fetch and logs the failure at most once a minute.
        Raises ``error`` when there is no built chain.
        """

        built = self._built
        if built is None:
            raise error

        now = time.monotonic()
        if self._fetch_failed_at is None or now - self._fetch_failed_at >= 60:
            self._fetch_failed_at = now
            logger.exception(
                "Failed to fetch Langfuse prompt %r, keeping version %s", self._prompt_name, built.prompt.version
            )
        return built.chain

    def _rebuild(self, prompt: PromptClient) -> Runnable[dict[str, Any], Output]:
        """
        Builds the chain for ``prompt`` under the lock.
        While another thread builds, returns the previous chain, or waits when there is none.
        """

        previous = self._built
        if not self._lock.acquire(blocking=previous is None):
            return cast("_Built", previous).chain

        try:
            chain = self._current(prompt)
            if chain is not None:
                return chain

            previous = self._built
            try:
                chain = self._build(prompt)
            except ChainBuildError as exc:
                self._failed = _Failure(prompt, time.monotonic(), exc)
                if previous is None:
                    raise
                logger.exception(
                    "Failed to build Langfuse prompt %r version %s, keeping version %s",
                    prompt.name,
                    prompt.version,
                    previous.prompt.version,
                )
                return previous.chain

            self._built = _Built(prompt, chain)
            self._failed = None
            return chain

        finally:
            self._lock.release()

    def _current(self, prompt: PromptClient) -> Runnable[dict[str, Any], Output] | None:
        """
        Returns the chain that serves ``prompt`` without a build, or ``None`` when a build is due.

        A prompt that failed to build less than a minute ago is served by the previous chain, or
        raises its error again when there is none.
        """

        built = self._built
        if built is not None and (built.prompt is prompt or _same_prompt(built.prompt, prompt)):
            return built.chain

        failed = self._failed
        if failed is None or not _same_prompt(failed.prompt, prompt) or time.monotonic() - failed.at >= 60:
            return None
        if built is None:
            raise ChainBuildError(str(failed.error)) from failed.error
        return built.chain

    def _build(self, prompt: PromptClient) -> Runnable[dict[str, Any], Output]:
        """
        Builds ``template | model`` for ``prompt`` and wraps any failure into ``ChainBuildError``.
        """

        try:
            # The template metadata and the hooks get a copy, so they cannot change the SDK cache.
            prompt_copy = copy.deepcopy(prompt)
            model = self._build_model(prompt_copy)
            template = LangfusePromptTemplate.from_prompt(prompt_copy)
            chain = (template | model).with_config(run_name=self._prompt_name)
        except Exception as exc:
            raise ChainBuildError(
                f"Failed to build chain for Langfuse prompt {prompt.name!r} version {prompt.version}: {exc}"
            ) from exc

        return cast("Runnable[dict[str, Any], Output]", chain)

    def _build_model(self, prompt: PromptClient) -> Runnable[LanguageModelInput, Any]:
        """
        Creates the chat model from the prompt config and applies the hooks.
        """

        params = build_model_params(
            prompt.config,
            allowed_keys=self._allowed_config_keys,
            model_kwargs=self._model_kwargs,
            provider_kwargs=self._provider_kwargs,
        )
        model: Runnable[LanguageModelInput, Any] = init_chat_model(**params)

        for hook, accepts_prompt in self._hooks:
            model = hook(model, prompt=prompt) if accepts_prompt else hook(model)
        return model


def _same_prompt(a: PromptClient, b: PromptClient) -> bool:
    """
    Returns whether two prompts have the same name, version, content and config.
    """

    return a.name == b.name and a.version == b.version and a.prompt == b.prompt and a.config == b.config


def _accepts_prompt(hook: Callable[..., Any]) -> bool:
    """
    Returns whether ``hook`` has a parameter named ``prompt``.
    """

    try:
        return "prompt" in inspect.signature(hook).parameters
    except (TypeError, ValueError):
        return False
