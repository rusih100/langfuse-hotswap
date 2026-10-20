"""
The factory: create arguments, model selection and the config allowlist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

import pytest

from pydantic import model_validator

from langfuse_hotswap import ChainBuildError, LangfuseChainFactory, LangfusePromptRunnable

from .fakes import FakeChatModel

if TYPE_CHECKING:
    from .fakes import FakeLangfuse


def built_model(chain: LangfusePromptRunnable[Any]) -> FakeChatModel:
    """
    Returns the model of the chain ``chain`` has built.
    """

    return cast("Any", chain._prompts._built).value.steps[1]


# Create


def test_create_returns_runnable(factory: LangfuseChainFactory) -> None:
    """
    create returns a working LangfusePromptRunnable.
    """

    chain = factory.create("culinary")

    assert isinstance(chain, LangfusePromptRunnable)
    assert chain.invoke({"dish": "borscht"}).content == "fake-1|0.1|Ingredients of borscht|"


def test_label_is_passed_to_get_prompt(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    label reaches get_prompt and version stays unset.
    """

    factory.create("culinary", label="staging").invoke({"dish": "borscht"})

    assert client.calls[0]["label"] == "staging"
    assert client.calls[0]["version"] is None


def test_version_is_passed_to_get_prompt(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    version reaches get_prompt and label stays unset.
    """

    factory.create("culinary", version=3).invoke({"dish": "borscht"})

    assert client.calls[0]["version"] == 3
    assert client.calls[0]["label"] is None


def test_label_and_version_together_are_rejected_at_create(factory: LangfuseChainFactory) -> None:
    """
    label and version together are rejected by create.
    """

    with pytest.raises(ValueError, match="label and version"):
        factory.create("culinary", label="staging", version=3)


def test_empty_prompt_name_is_rejected_at_create(factory: LangfuseChainFactory) -> None:
    """
    An empty prompt name is rejected by create.
    """

    with pytest.raises(ValueError, match="empty"):
        factory.create("")


def test_get_prompt_kwargs_are_passed_through(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    Keyword arguments of create other than label and version reach get_prompt as they are.
    """

    factory.create("culinary", cache_ttl_seconds=300, max_retries=1, fetch_timeout_seconds=2).invoke({"dish": "x"})

    assert client.calls == [
        {
            "name": "culinary",
            "label": None,
            "version": None,
            "cache_ttl_seconds": 300,
            "max_retries": 1,
            "fetch_timeout_seconds": 2,
        }
    ]


def test_factory_template_format_is_the_default_for_every_prompt(client: FakeLangfuse) -> None:
    """
    The factory template_format renders the prompts whose config does not name one.
    """

    factory = LangfuseChainFactory(
        cast("Any", client), {"fake": FakeChatModel(model="fake-1")}, template_format="f-string"
    )
    client.messages = [("user", "Ingredients of {dish}")]
    client.config = {}

    result = factory.create("culinary").invoke({"dish": "borscht"})

    assert result.content == "fake-1|None|Ingredients of borscht|"


def test_factory_label_is_the_default_for_create(client: FakeLangfuse) -> None:
    """
    The factory label is used when create gets neither a label nor a version, and only then.
    """

    factory = LangfuseChainFactory(cast("Any", client), {"fake": FakeChatModel(model="fake-0")}, label="staging")

    factory.create("culinary").invoke({"dish": "x"})
    factory.create("culinary", label="latest").invoke({"dish": "x"})
    factory.create("culinary", version=3).invoke({"dish": "x"})

    assert [(c["label"], c["version"]) for c in client.calls] == [("staging", None), ("latest", None), (None, 3)]


# Models and allowlist


def test_models_must_not_be_empty(client: FakeLangfuse) -> None:
    """
    A factory without models is rejected.
    """

    with pytest.raises(ValueError, match="models"):
        LangfuseChainFactory(cast("Any", client), {})


def test_allowed_config_keys_rejects_a_string(client: FakeLangfuse) -> None:
    """
    A string other than "any" as allowed_config_keys is rejected instead of being split into characters.
    """

    with pytest.raises(TypeError):
        LangfuseChainFactory(cast("Any", client), {"fake": FakeChatModel(model="fake-0")}, allowed_config_keys="model")


def test_by_default_the_config_overrides_nothing(client: FakeLangfuse) -> None:
    """
    Without allowed_config_keys the model is used as built in the code, whatever the config says.
    """

    base = FakeChatModel(model="fake-0", temperature=0.5)
    factory = LangfuseChainFactory(cast("Any", client), {"fake": base})
    client.config = {"provider": "fake", "model": "fake-1", "temperature": 0.1, "max_tokens": 10}

    result = factory.create("culinary").invoke({"dish": "borscht"})

    assert result.content == "fake-0|0.5|Ingredients of borscht|"


def test_any_lets_the_config_override_every_field(client: FakeLangfuse) -> None:
    """
    With "any" every config key is passed to the model constructor.
    """

    factory = LangfuseChainFactory(
        cast("Any", client), {"fake": FakeChatModel(model="fake-0")}, allowed_config_keys="any"
    )
    client.config = {"provider": "fake", "model": "fake-1", "temperature": 0.1, "max_tokens": 10}

    chain = factory.create("culinary")
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    model = built_model(chain)
    assert model.max_tokens == 10


def test_allowed_config_keys_pass_only_those_keys(client: FakeLangfuse) -> None:
    """
    Only the listed config keys override the model fields.
    """

    base = FakeChatModel(model="fake-0", temperature=0.5)
    factory = LangfuseChainFactory(cast("Any", client), {"fake": base}, allowed_config_keys={"temperature"})
    client.config = {"provider": "fake", "model": "fake-1", "temperature": 0.1, "max_tokens": 10}

    chain = factory.create("culinary")
    result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-0|0.1|Ingredients of borscht|"
    assert built_model(chain).max_tokens is None


def test_config_keys_are_passed_as_constructor_arguments(client: FakeLangfuse) -> None:
    """
    A config key is a constructor argument, so the alias ``model`` sets ``model_name`` and the base model is untouched.
    """

    base = FakeChatModel(model="fake-0", temperature=0.5)
    factory = LangfuseChainFactory(cast("Any", client), {"fake": base}, allowed_config_keys={"model"})
    client.config = {"model": "fake-1"}

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})

    model = built_model(chain)
    assert model is not base
    assert (model.model_name, model.temperature) == ("fake-1", 0.5)
    assert base.model_name == "fake-0"


def test_an_overridden_field_is_passed_once_under_the_config_key(client: FakeLangfuse) -> None:
    """
    A field the config sets by alias is not also passed by name, so the config value wins in the constructor.
    """

    class Recording(FakeChatModel):
        """
        Fake model that records the arguments its constructor receives.
        """

        received: ClassVar[list[dict[str, Any]]] = []

        @model_validator(mode="before")
        @classmethod
        def record(cls, values: dict[str, Any]) -> dict[str, Any]:
            cls.received.append(dict(values))
            return values

    factory = LangfuseChainFactory(cast("Any", client), {"fake": Recording(model="fake-0")}, allowed_config_keys="any")
    client.config = {"model": "fake-1", "temperature": 0.3}

    factory.create("culinary").invoke({"dish": "borscht"})

    assert Recording.received[-1]["model"] == "fake-1"
    assert "model_name" not in Recording.received[-1]
    assert Recording.received[-1]["max_tokens"] is None


def test_without_overrides_the_base_model_is_used_as_is(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A config with only the selectors provider and template_format builds the chain on the model object itself.
    """

    client.config = {"provider": "fake", "template_format": "langfuse"}

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})

    assert built_model(chain) is factory._models["fake"]


def test_non_dict_config_selects_the_base_model(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A config that is not a dict is treated as empty.
    """

    client.config = None

    assert factory.create("culinary").invoke({"dish": "borscht"}).content == "fake-0|None|Ingredients of borscht|"


def test_provider_selects_among_several_models(client: FakeLangfuse) -> None:
    """
    provider selects the model by its name in models.
    """

    models = {"openai": FakeChatModel(model="gpt"), "anthropic": FakeChatModel(model="claude")}
    factory = LangfuseChainFactory(cast("Any", client), models)
    client.config = {"provider": "anthropic"}

    assert factory.create("culinary").invoke({"dish": "borscht"}).content == "claude|None|Ingredients of borscht|"


def test_provider_is_required_with_several_models(client: FakeLangfuse) -> None:
    """
    Without provider in the config and with several models the build fails and names the models.
    """

    models = {"openai": FakeChatModel(model="gpt"), "anthropic": FakeChatModel(model="claude")}
    factory = LangfuseChainFactory(cast("Any", client), models)
    client.config = {}

    with pytest.raises(ChainBuildError, match=r"provider None is not one of \['anthropic', 'openai'\]"):
        factory.create("culinary").invoke({"dish": "borscht"})


def test_fallback_is_rejected_at_create(factory: LangfuseChainFactory) -> None:
    """
    create rejects fallback, since a fallback prompt cannot select a model.
    """

    with pytest.raises(TypeError, match="with_fallbacks"):
        factory.create("culinary", fallback=[{"role": "user", "content": "{{dish}}"}])


def test_non_string_provider_is_named_in_the_error(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A provider that is not a string fails the build with an error that names the value and the models.
    """

    client.config = {"provider": ["fake"]}

    with pytest.raises(ChainBuildError, match=r"provider \['fake'\] is not one of \['fake'\]"):
        factory.create("culinary").invoke({"dish": "borscht"})


def test_template_format_in_the_config_needs_the_allowlist(client: FakeLangfuse) -> None:
    """
    template_format in the config applies only when the allowlist names it; otherwise the factory one does.
    """

    client.messages = [("user", "Ingredients of {dish}")]
    client.config = {"provider": "fake", "template_format": "f-string"}
    locked = LangfuseChainFactory(cast("Any", client), {"fake": FakeChatModel(model="fake-0")})
    opened = LangfuseChainFactory(
        cast("Any", client), {"fake": FakeChatModel(model="fake-0")}, allowed_config_keys={"template_format"}
    )

    by_factory = locked.create("culinary").invoke({"dish": "borscht"})
    by_config = opened.create("culinary").invoke({"dish": "borscht"})

    assert by_factory.content == "fake-0|None|Ingredients of {dish}|"
    assert by_config.content == "fake-0|None|Ingredients of borscht|"


def test_unknown_provider_keeps_the_previous_chain(
    factory: LangfuseChainFactory, client: FakeLangfuse, caplog: pytest.LogCaptureFixture
) -> None:
    """
    A provider outside models fails the build and the previous chain keeps serving.
    """

    chain = factory.create("culinary")
    chain.invoke({"dish": "borscht"})
    client.version = 2
    client.config = {"provider": "ollama", "model": "llama"}

    with caplog.at_level("ERROR", logger="langfuse_hotswap"):
        result = chain.invoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert "provider 'ollama' is not one of ['fake']" in caplog.text


def test_rejected_config_value_is_a_build_error(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A config value the model constructor rejects fails the build with the validation error as the cause.
    """

    client.config = {"temperature": "hot"}

    with pytest.raises(ChainBuildError, match="temperature"):
        factory.create("culinary").invoke({"dish": "borscht"})
