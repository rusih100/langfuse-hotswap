"""
Watch the model switch: run this, then move the ``production`` label in Langfuse to a version with another model.
"""

import time

from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

factory = LangfuseChainFactory(get_client())
chain = factory.create("support-reply", cache_ttl_seconds=5)

question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}

while True:
    message = chain.invoke(question)
    model = message.response_metadata.get("model_name") or message.response_metadata.get("model")
    print(f"{time.strftime('%H:%M:%S')} {model}: {str(message.content)[:80]}")
    time.sleep(3)
