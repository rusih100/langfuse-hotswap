"""
Model parameters assembled from the Langfuse prompt config and the factory kwargs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_ALLOWED_CONFIG_KEYS = frozenset(
    {
        "model",
        "model_provider",
        "temperature",
        "max_tokens",
        "max_output_tokens",
        "max_completion_tokens",
        "top_p",
        "top_k",
        "stop",
        "stop_sequences",
        "seed",
        "n",
        "frequency_penalty",
        "presence_penalty",
        "repetition_penalty",
        "logprobs",
        "top_logprobs",
        "logit_bias",
        "reasoning_effort",
        "reasoning",
        "thinking",
        "verbosity",
        "response_format",
        "streaming",
        "disable_streaming",
    }
)


def build_model_params(
    config: object,
    *,
    allowed_keys: frozenset[str] | None,
    model_kwargs: Mapping[str, Any],
    provider_kwargs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """
    Returns the ``init_chat_model`` arguments for a prompt config.

    Precedence, lowest first: the config, ``model_kwargs``, the kwargs of the selected provider.
    The config must name ``model`` and ``model_provider``.
    """

    raw_config = config if isinstance(config, dict) else {}
    params: dict[str, Any] = {
        key: value
        for key, value in raw_config.items()
        if not is_blocked_config_key(key) and (allowed_keys is None or key in allowed_keys)
    }
    params.update(model_kwargs)

    model = params.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("no 'model' in the prompt config")

    provider = params.get("model_provider")
    if not isinstance(provider, str) or not provider:
        raise ValueError("no 'model_provider' in the prompt config: the provider must be named explicitly")

    provider = normalize_provider(provider)
    if provider_kwargs and provider not in provider_kwargs:
        raise ValueError(f"provider {provider!r} is not configured in the factory: {sorted(provider_kwargs)}")

    return {**params, "model_provider": provider, **provider_kwargs.get(provider, {})}


def normalize_provider(provider: str) -> str:
    """
    Normalizes a provider name like ``init_chat_model`` does: ``Google-GenAI`` becomes ``google_genai``.
    """

    return provider.replace("-", "_").lower()


def is_blocked_config_key(key: str) -> bool:
    """
    Returns whether ``key`` is never taken from the prompt config, whatever the allowlist says.

    Blocked are endpoints, regions, projects, credentials, TLS settings, headers, proxies,
    transports, timeouts, retries, HTTP clients, passthrough dicts, callbacks, caches and the
    ``init_chat_model`` arguments that make the model configurable at run time.
    """

    return (
        key
        in {
            "configurable_fields",
            "config_prefix",
            "base_url",
            "url",
            "endpoint",
            "api_key",
            "apikey",
            "api_base",
            "api_endpoint",
            "api_transport",
            "token",
            "password",
            "username",
            "credential",
            "credentials",
            "organization",
            "project",
            "location",
            "region",
            "region_name",
            "project_id",
            "space_id",
            "instance_id",
            "deployment_id",
            "verify",
            "timeout",
            "max_retries",
            "transport",
            "headers",
            "proxy",
            "proxies",
            "client_options",
            "default_headers",
            "default_query",
            "default_metadata",
            "model_kwargs",
            "client",
            "async_client",
            "http_client",
            "http_async_client",
            "config",
            "cache",
            "callbacks",
            "rate_limiter",
            "custom_get_token_ids",
        }
        or key.startswith(("aws_", "extra_", "azure_ad_", "http_", "proxy_", "ssl_", "tls_"))
        or key.endswith(
            (
                "_api_key",
                "_api_base",
                "_api_url",
                "_base_url",
                "_url",
                "_endpoint",
                "_headers",
                "_client",
                "_proxy",
                "_proxies",
                "_options",
                "_kwargs",
                "_token",
                "_token_provider",
                "_profile_name",
                "_organization",
                "_metadata",
                "_timeout",
                "_retries",
            )
        )
    )
