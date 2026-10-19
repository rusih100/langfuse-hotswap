"""
Decide in the code what the prompt config may change.
"""

import os

from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

factory = LangfuseChainFactory(
    get_client(),
    # Passed to every provider; the prompt config cannot override them.
    timeout=30,
    max_retries=2,
    # The config may select only these providers, with these credentials.
    providers={
        "openai": {"api_key": os.environ["OPENAI_API_KEY"]},
        "anthropic": {"api_key": os.environ["ANTHROPIC_API_KEY"]},
    },
    # Only these config keys reach the model.
    allowed_config_keys={"model", "model_provider", "temperature", "max_tokens"},
)
chain = factory.create("support-reply")

message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"})
print(message.content)
