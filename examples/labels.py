"""
Select the prompt version by label or number.
"""

from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

factory = LangfuseChainFactory(get_client())

production = factory.create("support-reply")
staging = factory.create("support-reply", label="staging")
pinned = factory.create("support-reply", version=1)

question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}
for name, chain in [("production", production), ("staging", staging), ("pinned", pinned)]:
    print(f"{name:>10}: {str(chain.invoke(question).content)[:80]}")
