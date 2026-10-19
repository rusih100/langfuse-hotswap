"""
Factory that shares the Langfuse client and the model kwargs between runnables.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langfuse_hotswap._config import DEFAULT_ALLOWED_CONFIG_KEYS, normalize_provider
from langfuse_hotswap._runnable import LangfusePromptRunnable

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from langchain_core.messages import BaseMessage
    from langfuse import Langfuse
    from langfuse.model import ChatMessageDict


class LangfuseChainFactory:
    """
    Creates ``LangfusePromptRunnable`` instances that share the Langfuse client and the model kwargs.
    """

    def __init__(
        self,
        client: Langfuse,
        *,
        providers: Mapping[str, Mapping[str, Any]] | None = None,
        allowed_config_keys: Iterable[str] | None = DEFAULT_ALLOWED_CONFIG_KEYS,
        **model_kwargs: Any,
    ) -> None:
        """
        ``model_kwargs`` are passed to every provider, ``providers`` maps a provider name to the
        kwargs passed only to that provider. Both override the prompt config.

        Only ``allowed_config_keys`` are taken from the config; ``None`` takes every key that is not
        blocked by ``is_blocked_config_key``. With ``providers`` the config may select only them.
        """

        if isinstance(allowed_config_keys, str):
            raise TypeError("allowed_config_keys must be a collection of strings, not a string")

        self._client = client
        self._providers = {normalize_provider(name): dict(kwargs) for name, kwargs in (providers or {}).items()}
        self._allowed_config_keys = None if allowed_config_keys is None else frozenset(allowed_config_keys)
        self._model_kwargs = model_kwargs

    def create(
        self,
        prompt_name: str,
        *,
        label: str | None = None,
        version: int | None = None,
        cache_ttl_seconds: int | None = None,
        fallback: str | list[ChatMessageDict] | None = None,
        max_retries: int | None = None,
        fetch_timeout_seconds: int | None = None,
    ) -> LangfusePromptRunnable[BaseMessage]:
        """
        Returns a runnable for ``prompt_name``.

        ``label`` or ``version`` selects the prompt, the ``production`` label by default. The other
        arguments are passed to ``get_prompt``; ``fallback`` is a string for a text prompt and a list
        of messages for a chat prompt.
        """

        if not prompt_name:
            raise ValueError("prompt_name must not be empty")
        if label is not None and version is not None:
            raise ValueError("label and version cannot be used together")

        return LangfusePromptRunnable(
            self._client,
            prompt_name,
            prompt_kwargs={
                "label": label,
                "version": version,
                "type": "chat" if isinstance(fallback, list) else "text",
                "cache_ttl_seconds": cache_ttl_seconds,
                "fallback": fallback,
                "max_retries": max_retries,
                "fetch_timeout_seconds": fetch_timeout_seconds,
            },
            model_kwargs=self._model_kwargs,
            provider_kwargs=self._providers,
            allowed_config_keys=self._allowed_config_keys,
        )
