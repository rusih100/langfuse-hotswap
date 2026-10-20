"""
Trace the calls into Langfuse, linked to the prompt version.
"""

from langchain_openai import ChatOpenAI
from langfuse import get_client
from langfuse.langchain import CallbackHandler

from langfuse_hotswap import LangfuseChainFactory

langfuse = get_client()
factory = LangfuseChainFactory(langfuse, models={"openai": ChatOpenAI(model="gpt-5.5")})
chain = factory.create("support-reply")

message = chain.invoke(
    {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"},
    config={"callbacks": [CallbackHandler()], "metadata": {"langfuse_user_id": "alice"}},
)
print(message.content)

langfuse.flush()
