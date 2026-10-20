"""
Runnable that rebuilds ``prompt | model`` when the Langfuse prompt changes.
"""

from __future__ import annotations

import copy
import inspect

from typing import TYPE_CHECKING, Any, cast, overload

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig
from typing_extensions import TypeVar

from langfuse_hotswap._errors import ChainBuildError, HotswapError
from langfuse_hotswap._template import LangfusePromptTemplate

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator, Sequence

    from langchain_core.language_models import BaseChatModel, LanguageModelInput
    from langchain_core.tools import BaseTool
    from langchain_core.utils.pydantic import TypeBaseModel
    from langfuse.model import PromptClient
    from pydantic import BaseModel

    from langfuse_hotswap._prompts import PromptManager
    from langfuse_hotswap._template import TemplateFormat

Output = TypeVar("Output", default=BaseMessage)
Schema = TypeVar("Schema", bound="BaseModel")


class LangfusePromptRunnable(Runnable[dict[str, Any], Output]):
    """
    Renders a Langfuse prompt and runs it through the chat model selected by the prompt config.

    Every call resolves the chain through ``PromptManager`` and delegates to ``template | model``
    built for the current prompt.
    """

    def __init__(
        self,
        prompts: PromptManager[Runnable[dict[str, Any], Any]],
        model_for: Callable[[PromptClient], BaseChatModel],
        template_format_for: Callable[[PromptClient], TemplateFormat],
    ) -> None:
        """
        ``model_for`` returns the chat model for a prompt, ``template_format_for`` its renderer.
        """

        self.name = prompts.name
        self._prompts = prompts
        self._model_for = model_for
        self._template_format_for = template_format_for
        self._hooks: tuple[Callable[..., Runnable[LanguageModelInput, Any]], ...] = ()

    # Model customization: every method returns a copy, the hooks are applied at build time.

    def with_model(self, hook: Callable[..., Runnable[LanguageModelInput, Any]]) -> LangfusePromptRunnable[Any]:
        """
        Returns a copy whose model is replaced by ``hook(model)``.

        A hook with a ``prompt`` parameter is called as ``hook(model, prompt=prompt)`` with a copy of
        the Langfuse prompt client.
        """

        clone = self._clone()
        clone._hooks = (*self._hooks, hook)
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
        Returns a copy with the same settings and hooks and an empty cache.
        """

        clone: LangfusePromptRunnable[Any] = LangfusePromptRunnable(
            self._prompts.copy(), self._model_for, self._template_format_for
        )
        clone._hooks = self._hooks
        return clone

    def _prepare(self) -> Runnable[dict[str, Any], Output]:
        """
        Returns the chain for the current prompt.
        """

        return self._prompts.resolve(self._build)

    async def _aprepare(self, config: RunnableConfig | None) -> Runnable[dict[str, Any], Output]:
        """
        Returns the chain for the current prompt without blocking the event loop on HTTP.
        """

        return await self._prompts.aresolve(self._build, config)

    def _build(self, prompt: PromptClient) -> Runnable[dict[str, Any], Output]:
        """
        Builds ``template | model`` for ``prompt`` and wraps any failure into ``ChainBuildError``.
        """

        try:
            # The template metadata and the hooks get a copy, so they cannot change the SDK cache.
            prompt_copy = copy.deepcopy(prompt)
            model: Runnable[LanguageModelInput, Any] = self._model_for(prompt_copy)

            for hook in self._hooks:
                model = hook(model, prompt=prompt_copy) if _accepts_prompt(hook) else hook(model)

            template = LangfusePromptTemplate.from_prompt(prompt_copy, self._template_format_for(prompt_copy))
            chain = (template | model).with_config(run_name=self.name)

        except Exception as exc:
            raise ChainBuildError(
                f"Failed to build chain for Langfuse prompt {prompt.name!r} version {prompt.version}: {exc}"
            ) from exc

        return cast("Runnable[dict[str, Any], Output]", chain)


def _accepts_prompt(hook: Callable[..., Any]) -> bool:
    """
    Returns whether ``hook`` has a parameter named ``prompt``.
    """

    try:
        return "prompt" in inspect.signature(hook).parameters
    except (TypeError, ValueError):
        return False
