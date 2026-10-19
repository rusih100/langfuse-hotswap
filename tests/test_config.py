"""
Model parameters: the provider, the precedence of the sources, the allowlist and the blocked keys.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

from langchain.chat_models import base

from langfuse_hotswap import ChainBuildError, HotswapError, LangfuseChainFactory

from .fakes import FakeChatModel

if TYPE_CHECKING:
    from .fakes import FakeLangfuse


# Model and provider


def test_model_is_built_from_prompt_config(
    factory: LangfuseChainFactory, client: FakeLangfuse, init_calls: list[dict[str, Any]]
) -> None:
    """
    The prompt config is passed to init_chat_model as is.
    """

    result = factory.create("culinary").invoke({"dish": "borscht"})

    assert result.content == "fake-1|0.1|Ingredients of borscht|"
    assert init_calls == [client.config]


def test_missing_model_raises_with_name_and_version(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A config without model fails to build, and the error names the prompt and the version.
    """

    client.config = {"temperature": 0.1}
    client.version = 7

    with pytest.raises(ChainBuildError, match=r"'culinary' version 7.*no 'model'"):
        factory.create("culinary").invoke({"dish": "borscht"})


def test_non_dict_config_is_treated_as_empty(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    A config that is not a dict is treated as empty and fails to build.
    """

    client.config = None

    with pytest.raises(ChainBuildError):
        factory.create("culinary").invoke({"dish": "borscht"})


def test_model_constructor_error_is_wrapped(factory: LangfuseChainFactory, client: FakeLangfuse) -> None:
    """
    An error of the model constructor becomes ChainBuildError with the original as the cause.
    """

    client.config = {"model": "fake-1", "model_provider": "fake", "fail": True}

    with pytest.raises(ChainBuildError, match="provider is down") as info:
        factory.create("culinary").invoke({"dish": "borscht"})

    assert isinstance(info.value, HotswapError)
    assert isinstance(info.value.__cause__, RuntimeError)


def test_model_name_is_passed_as_is(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    The model name reaches the model unchanged, colons and provider prefix included.
    """

    factory = LangfuseChainFactory(cast("Any", client), allowed_config_keys=None, providers={"openai": {}})
    client.config = {"model": "openai:ft:qwen:org::id", "model_provider": "openai"}

    factory.create("culinary").invoke({"dish": "borscht"})

    assert init_calls == [{"model": "openai:ft:qwen:org::id", "model_provider": "openai"}]


@pytest.mark.parametrize("model", ["claude-sonnet-5-5", "fake:fake-1"])
def test_provider_is_never_inferred_from_the_model_name(
    factory: LangfuseChainFactory, client: FakeLangfuse, model: str
) -> None:
    """
    Without model_provider the build fails, whatever the model name looks like.
    """

    client.config = {"model": model}

    with pytest.raises(ChainBuildError, match="no 'model_provider'"):
        factory.create("culinary").invoke({"dish": "borscht"})


def test_providers_require_an_explicit_provider(client: FakeLangfuse) -> None:
    """
    With providers configured, a config without model_provider fails to build.
    """

    factory = LangfuseChainFactory(cast("Any", client), allowed_config_keys=None, providers={"openai": {}})
    client.config = {"model": "gpt-4o"}

    with pytest.raises(ChainBuildError, match="no 'model_provider'"):
        factory.create("culinary").invoke({"dish": "borscht"})


def test_code_can_pin_the_provider(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    model_provider in the factory kwargs overrides the one in the config.
    """

    factory = LangfuseChainFactory(cast("Any", client), model_provider="fake")
    client.config = {"model": "other:fake-1", "model_provider": "other"}

    factory.create("culinary").invoke({"dish": "borscht"})

    assert init_calls == [{"model": "other:fake-1", "model_provider": "fake"}]


def test_provider_names_are_normalized(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    Provider names in the config and in providers match regardless of case and dashes.
    """

    factory = LangfuseChainFactory(
        cast("Any", client), allowed_config_keys=None, providers={"google-genai": {"project": "p"}}
    )
    client.config = {"model": "gemini", "model_provider": "Google_GenAI"}

    factory.create("culinary").invoke({"dish": "borscht"})

    assert init_calls[0]["project"] == "p"


def test_provider_outside_providers_is_rejected(client: FakeLangfuse) -> None:
    """
    With providers configured, the config cannot select any other provider.
    """

    factory = LangfuseChainFactory(
        cast("Any", client), allowed_config_keys=None, providers={"openai": {"api_key": "K"}}, api_key="shared"
    )
    client.config = {"model": "claude", "model_provider": "anthropic"}

    with pytest.raises(ChainBuildError, match="'anthropic' is not configured"):
        factory.create("culinary").invoke({"dish": "borscht"})


# Precedence


def test_provider_kwargs_apply_to_matching_provider_only(
    client: FakeLangfuse, init_calls: list[dict[str, Any]]
) -> None:
    """
    Provider kwargs reach only the provider selected by the config, factory kwargs reach every provider.
    """

    factory = LangfuseChainFactory(
        cast("Any", client),
        providers={"fake": {"credentials": "fake-creds"}, "openai": {"base_url": "http://qwen"}},
        timeout=5,
    )
    chain = factory.create("culinary")

    chain.invoke({"dish": "borscht"})
    client.version = 2
    client.config = {"model": "qwen", "model_provider": "openai", "temperature": 0.5}
    chain.invoke({"dish": "borscht"})

    assert init_calls[0] == {
        "model": "fake-1",
        "model_provider": "fake",
        "temperature": 0.1,
        "credentials": "fake-creds",
        "timeout": 5,
    }
    assert init_calls[1] == {
        "model": "qwen",
        "model_provider": "openai",
        "temperature": 0.5,
        "base_url": "http://qwen",
        "timeout": 5,
    }


def test_code_overrides_prompt_config(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    Provider kwargs override factory kwargs, and both override the config.
    """

    factory = LangfuseChainFactory(
        cast("Any", client), allowed_config_keys=None, providers={"fake": {"temperature": 0.9}}, temperature=0.5
    )

    factory.create("culinary").invoke({"dish": "borscht"})

    assert init_calls[0]["temperature"] == 0.9


def test_prompt_config_cannot_redirect_requests(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    Endpoints and credentials set in code win over the ones in the config.
    """

    factory = LangfuseChainFactory(
        cast("Any", client),
        allowed_config_keys=None,
        providers={"fake": {"base_url": "https://trusted"}},
        api_key="secret",
    )
    client.config = {"model": "fake-1", "model_provider": "fake", "base_url": "https://evil", "api_key": "stolen"}

    factory.create("culinary").invoke({"dish": "borscht"})

    assert init_calls[0]["base_url"] == "https://trusted"
    assert init_calls[0]["api_key"] == "secret"


# Allowlist and blocked keys


def test_default_allowlist_passes_only_known_parameters(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    The default allowlist drops unknown keys, timeouts and retries.
    """

    client.config = {
        "model": "fake-1",
        "model_provider": "fake",
        "temperature": 0.1,
        "foo": 1,
        "user": "x",
        "timeout": 3600,
        "max_retries": 100,
    }

    LangfuseChainFactory(cast("Any", client)).create("culinary").invoke({"dish": "borscht"})

    assert init_calls == [{"model": "fake-1", "model_provider": "fake", "temperature": 0.1}]


def test_allowed_config_keys_drop_everything_else(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    Only the keys from allowed_config_keys reach the model.
    """

    factory = LangfuseChainFactory(cast("Any", client), allowed_config_keys={"model", "model_provider", "temperature"})
    client.config = {"model": "fake-1", "model_provider": "fake", "temperature": 0.1, "base_url": "https://evil"}

    factory.create("culinary").invoke({"dish": "borscht"})

    assert init_calls == [{"model": "fake-1", "model_provider": "fake", "temperature": 0.1}]


def test_blocked_config_keys_never_reach_the_model(client: FakeLangfuse, init_calls: list[dict[str, Any]]) -> None:
    """
    Blocked keys are dropped even when the allowlist names them.
    """

    client.config = {
        "model": "fake-1",
        "model_provider": "fake",
        "configurable_fields": "any",
        "config_prefix": "x",
        "base_url": "https://evil",
        "api_key": "stolen",
        "default_headers": {"x": "y"},
        "openai_api_base": "https://evil",
        "anthropic_api_url": "https://evil",
        "azure_endpoint": "https://evil",
        "openai_proxy": "https://evil",
        "http_client": "x",
    }
    factory = LangfuseChainFactory(cast("Any", client), allowed_config_keys=set(client.config))

    factory.create("culinary").invoke({"dish": "borscht"})

    assert init_calls == [{"model": "fake-1", "model_provider": "fake"}]


def test_passthrough_dicts_and_provider_credentials_are_blocked(
    client: FakeLangfuse, init_calls: list[dict[str, Any]]
) -> None:
    """
    Without an allowlist, passthrough dicts, credentials, endpoints, timeouts and retries are still dropped.
    """

    client.config = {
        "model": "fake-1",
        "model_provider": "fake",
        "model_kwargs": {"extra_headers": {"Authorization": "Bearer evil"}},
        "extra_headers": {"Authorization": "Bearer evil"},
        "extra_query": {"k": "v"},
        "extra_body": {"k": "v"},
        "client_kwargs": {"proxy": "http://evil"},
        "endpoint_url": "https://evil",
        "aws_secret_access_key": "x",
        "credentials_profile_name": "x",
        "azure_ad_token": "x",
        "url": "https://evil",
        "apikey": "x",
        "token": "x",
        "cache": True,
        "callbacks": [],
        "default_metadata": [("authorization", "x")],
        "config": {},
        "client_options": {"api_endpoint": "https://evil"},
        "verify": False,
        "transport": "rest",
        "api_transport": "rest",
        "headers": {"Authorization": "Bearer evil"},
        "proxies": {"https": "http://evil"},
        "proxy_url": "http://evil",
        "http_proxy": "http://evil",
        "ssl_verify": False,
        "region_name": "eu-west-1",
        "project": "other-project",
        "location": "europe-west1",
        "project_id": "x",
        "space_id": "x",
        "ollama_options": {"num_ctx": 1},
        "timeout": 3600,
        "request_timeout": 3600,
        "max_retries": 100,
        "stream_timeout": 3600,
        "num_retries": 100,
    }
    factory = LangfuseChainFactory(cast("Any", client), allowed_config_keys=None)

    factory.create("culinary").invoke({"dish": "borscht"})

    assert init_calls == [{"model": "fake-1", "model_provider": "fake"}]


def test_configurable_fields_from_config_do_not_make_the_model_configurable(
    client: FakeLangfuse, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    configurable_fields in the config do not turn the model into a configurable one.
    """

    monkeypatch.setattr("langfuse_hotswap._runnable.init_chat_model", base.init_chat_model)
    monkeypatch.setitem(base._BUILTIN_PROVIDERS, "fake", ("tests.fakes", "FakeChatModel", lambda cls, **kw: cls(**kw)))
    client.config = {"model": "fake-1", "model_provider": "fake", "configurable_fields": "any", "config_prefix": "p"}

    factory = LangfuseChainFactory(cast("Any", client), allowed_config_keys=None, providers={"fake": {}})

    model = factory.create("culinary")._build_model(client.get_prompt("culinary"))

    assert isinstance(model, FakeChatModel)
