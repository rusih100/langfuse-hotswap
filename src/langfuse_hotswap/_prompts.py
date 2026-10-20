"""
Fetches a Langfuse prompt and keeps the value built from it, rebuilding when the prompt changes.
"""

from __future__ import annotations

import logging
import threading

from typing import TYPE_CHECKING, Any, Generic, NamedTuple, TypeVar, cast

from langchain_core.runnables.config import run_in_executor

from langfuse_hotswap._errors import ChainBuildError, PromptFetchError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from langchain_core.runnables import RunnableConfig
    from langfuse import Langfuse
    from langfuse.model import PromptClient

T = TypeVar("T")


logger = logging.getLogger(__name__)


class _Built(NamedTuple, Generic[T]):
    """
    A built value and the prompt it was built from.
    """

    prompt: PromptClient
    value: T


class _Failure(NamedTuple):
    """
    A prompt that failed to build and the error.
    """

    prompt: PromptClient
    error: ChainBuildError


class PromptManager(Generic[T]):
    """
    Fetches one Langfuse prompt through the SDK cache and keeps the value built from it.

    The value is rebuilt under a lock when the prompt changes. A prompt that fails to build is not
    retried until the prompt changes, and the previous value serves the calls meanwhile. A failed
    fetch is served by the previous value and logged once per outage.
    """

    def __init__(self, client: Langfuse, prompt_name: str, prompt_kwargs: Mapping[str, Any]) -> None:
        """
        ``prompt_kwargs`` are passed to ``client.get_prompt``.
        """

        self.name = prompt_name
        self._client = client
        self._prompt_kwargs = prompt_kwargs

        self._lock = threading.RLock()
        self._built: _Built[T] | None = None
        self._failed: _Failure | None = None
        self._fetch_failed = False

    def copy(self) -> PromptManager[T]:
        """
        Returns a manager for the same prompt with an empty cache.
        """

        return PromptManager(self._client, self.name, self._prompt_kwargs)

    def resolve(self, build: Callable[[PromptClient], T]) -> T:
        """
        Returns the value for the current prompt, building it with ``build`` if the prompt changed.
        """

        if self._built is not None:
            return self._resolve(build)
        # On a cold start the SDK fetches over HTTP and does not deduplicate concurrent misses.
        with self._lock:
            return self._resolve(build)

    async def aresolve(self, build: Callable[[PromptClient], T], config: RunnableConfig | None) -> T:
        """
        Async ``resolve``: fetches on the event loop when the SDK cache is warm, otherwise in the executor.
        """

        if not self._cache_is_warm():
            return await run_in_executor(config, self.resolve, build)

        try:
            prompt = self._fetch()
        except PromptFetchError as exc:
            return self._serve_previous(exc)

        built = self._current(prompt)
        if built is None:
            return await run_in_executor(config, self._rebuild, prompt, build)
        return built.value

    def _resolve(self, build: Callable[[PromptClient], T]) -> T:
        """
        Fetches the prompt and returns the value for it, building it with ``build`` if the prompt changed.
        """

        try:
            prompt = self._fetch()
        except PromptFetchError as exc:
            return self._serve_previous(exc)

        built = self._current(prompt)
        if built is None:
            return self._rebuild(prompt, build)
        return built.value

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
            and not self._fetch_failed
        )

    def _fetch(self) -> PromptClient:
        """
        Fetches the prompt and wraps any failure into ``PromptFetchError``.
        """

        try:
            prompt = self._client.get_prompt(self.name, **self._prompt_kwargs)
        except Exception as exc:
            label = self._prompt_kwargs.get("label")
            version = self._prompt_kwargs.get("version")
            raise PromptFetchError(
                f"Failed to fetch Langfuse prompt {self.name!r} (label={label!r}, version={version!r}): {exc}"
            ) from exc

        self._fetch_failed = False
        return prompt

    def _serve_previous(self, error: PromptFetchError) -> T:
        """
        Returns the built value after a failed fetch and logs the first failure of an outage.
        Raises ``error`` when there is no built value.
        """

        built = self._built
        if built is None:
            raise error

        if not self._fetch_failed:
            logger.exception(
                "Failed to fetch Langfuse prompt %r, keeping version %s until it is reachable again",
                self.name,
                built.prompt.version,
            )
        self._fetch_failed = True
        return built.value

    def _current(self, prompt: PromptClient) -> _Built[T] | None:
        """
        Returns the built value that serves ``prompt``, or ``None`` when a build is due.

        A prompt that failed to build is served by the previous value, or raises its error again
        when there is none.
        """

        built = self._built
        if built is not None and (built.prompt is prompt or self._same_prompt(built.prompt, prompt)):
            return built

        failed = self._failed
        if failed is None or not self._same_prompt(failed.prompt, prompt):
            return None
        if built is None:
            raise ChainBuildError(str(failed.error)) from failed.error
        return built

    def _rebuild(self, prompt: PromptClient, build: Callable[[PromptClient], T]) -> T:
        """
        Builds the value for ``prompt`` under the lock.
        While another thread builds, returns the previous value, or waits when there is none.
        """

        previous = self._built
        if not self._lock.acquire(blocking=previous is None):
            return cast("_Built[T]", previous).value

        try:
            built = self._current(prompt)
            if built is not None:
                return built.value

            previous = self._built
            try:
                value = build(prompt)
            except ChainBuildError as exc:
                self._failed = _Failure(prompt, exc)
                if previous is None:
                    raise
                logger.exception(
                    "Failed to build Langfuse prompt %r version %s, keeping version %s",
                    prompt.name,
                    prompt.version,
                    previous.prompt.version,
                )
                return previous.value

            self._built = _Built(prompt, value)
            self._failed = None
            return value

        finally:
            self._lock.release()

    @staticmethod
    def _same_prompt(a: PromptClient, b: PromptClient) -> bool:
        """
        Returns whether two prompts have the same name, version, content and config.
        """

        return a.name == b.name and a.version == b.version and a.prompt == b.prompt and a.config == b.config
