"""
Factory that shares the Langfuse client, the chat models and the config allowlist between runnables.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from langfuse_hotswap._prompts import PromptManager
from langfuse_hotswap._runnable import LangfusePromptRunnable

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from langchain_core.language_models import BaseChatModel, LanguageModelInput
    from langchain_core.messages import BaseMessage
    from langchain_core.runnables import Runnable
    from langfuse import Langfuse
    from langfuse.model import PromptClient

    from langfuse_hotswap._template import TemplateFormat


class LangfuseChainFactory:
    """
    Creates ``LangfusePromptRunnable`` instances over the chat models built in the code.
    """

    def __init__(
        self,
        client: Langfuse,
        models: Mapping[str, BaseChatModel],
        *,
        allowed_config_keys: Iterable[str] | Literal["any"] | None = None,
        label: str | None = None,
        template_format: TemplateFormat = "langfuse",
        hooks: Iterable[Callable[..., Runnable[LanguageModelInput, Any]]] | None = None,
    ) -> None:
        """
        ``models`` maps a name to a chat model; the prompt config selects one of them with ``provider``.

        ``allowed_config_keys`` names the model fields the config may override: ``None`` lets it
        override nothing, ``"any"`` every field. ``label`` is the prompt label ``create`` uses when
        it is given neither a label nor a version. ``template_format`` renders the prompts whose
        config does not name one, or may not. ``hooks`` are applied to the model of every runnable
        after its own ``with_model`` hooks.
        """

        if not models:
            raise ValueError("models must not be empty")
        if isinstance(allowed_config_keys, str) and allowed_config_keys != "any":
            raise TypeError("allowed_config_keys must be a collection of strings, 'any' or None")
        if callable(hooks):
            raise TypeError("hooks must be a collection of hooks, wrap a single hook in a list")

        self._client = client
        self._models = dict(models)
        self._allowed = "any" if allowed_config_keys == "any" else frozenset(allowed_config_keys or ())
        self._default_provider = next(iter(self._models)) if len(self._models) == 1 else None
        self._label = label
        self._template_format = template_format
        self._hooks = tuple(hooks or ())

    def create(
        self,
        prompt_name: str,
        *,
        label: str | None = None,
        version: int | None = None,
        **get_prompt_kwargs: Any,
    ) -> LangfusePromptRunnable[BaseMessage]:
        """
        Returns a runnable for ``prompt_name``.

        ``label`` or ``version`` selects the prompt; without both, the factory label, or the
        ``production`` label. ``get_prompt_kwargs``, such as ``cache_ttl_seconds``, are passed to
        ``client.get_prompt``.
        """

        if not prompt_name:
            raise ValueError("prompt_name must not be empty")
        if label is not None and version is not None:
            raise ValueError("label and version cannot be used together")
        if label is None and version is None:
            label = self._label
        if "fallback" in get_prompt_kwargs:
            raise TypeError("fallback is not supported, use with_fallbacks with a local chain for a cold start")

        prompt_kwargs = {"label": label, "version": version, **get_prompt_kwargs}
        prompts: PromptManager[Any] = PromptManager(self._client, prompt_name, prompt_kwargs)
        return LangfusePromptRunnable(
            prompts,
            self._model_for,
            self._template_format_for,
            default_hooks=self._hooks,
        )

    def _model_for(self, prompt: PromptClient) -> BaseChatModel:
        """
        Returns the model selected by ``provider`` in the prompt config with the allowed config keys applied.

        Without ``provider`` the only model is selected. The config keys other than ``provider`` and
        ``template_format`` are passed to the constructor of the model class together with the
        fields of the selected model.
        """

        config = self._config(prompt)
        name = config.get("provider", self._default_provider)
        if not isinstance(name, str) or name not in self._models:
            raise ValueError(f"provider {name!r} is not one of {sorted(self._models)}")

        base = self._models[name]
        params = {k: v for k, v in config.items() if k not in ("provider", "template_format") and self._allows(k)}
        if not params:
            return base

        # A field the config sets, by name or alias, is left out, so the config value wins whatever a validator prefers.
        model_fields = type(base).model_fields
        fields = {
            field: value
            for field, value in base.__dict__.items()
            if field in model_fields and field not in params and model_fields[field].alias not in params
        }
        return type(base)(**{**fields, **params})

    def _template_format_for(self, prompt: PromptClient) -> TemplateFormat:
        """
        Returns ``template_format`` from the prompt config when the allowlist permits it, else the factory one.
        """

        config = self._config(prompt)
        if "template_format" in config and self._allows("template_format"):
            return config["template_format"]
        return self._template_format

    def _allows(self, key: str) -> bool:
        """
        Returns whether the config may set ``key``.
        """

        return self._allowed == "any" or key in self._allowed

    @staticmethod
    def _config(prompt: PromptClient) -> dict[str, Any]:
        """
        Returns the prompt config, an empty dict when it is not a dict.
        """

        return prompt.config if isinstance(prompt.config, dict) else {}
