"""
Select the prompt version by label or number.
"""

from langchain_openai import ChatOpenAI
from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

# Without a label of its own, every chain of this factory follows "staging".
factory = LangfuseChainFactory(get_client(), models={"openai": ChatOpenAI(model="gpt-5.5")}, label="staging")

staging = factory.create("support-reply")
production = factory.create("support-reply", label="production")
pinned = factory.create("support-reply", version=1)

question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}
for name, chain in [("production", production), ("staging", staging), ("pinned", pinned)]:
    print(f"{name:>10}: {str(chain.invoke(question).content)[:80]}")
