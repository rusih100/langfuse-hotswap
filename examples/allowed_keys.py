"""
Decide in the code which model fields the prompt config may change.
"""

import os

from langchain_openai import ChatOpenAI
from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

factory = LangfuseChainFactory(
    get_client(),
    # The config selects one of these with "provider"; credentials, endpoints and timeouts stay here.
    models={
        "openai": ChatOpenAI(model="gpt-5.5", api_key=os.environ["OPENAI_API_KEY"], timeout=30),
        "ollama": ChatOpenAI(model="llama3", base_url="http://localhost:11434/v1", api_key="ollama"),
    },
    # Only these config keys override the model fields. Without the argument the config changes nothing.
    allowed_config_keys={"model", "temperature", "max_tokens"},
)
chain = factory.create("support-reply")

message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"})
print(message.content)
