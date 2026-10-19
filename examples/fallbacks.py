"""
Keep answering when Langfuse is unreachable on a cold start.
"""

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory, PromptFetchError

factory = LangfuseChainFactory(get_client())
question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}

# Once a chain is built it keeps serving through outages and broken versions on its own.
# A fallback is for the cold start, when there is no chain yet.

# Option 1: a fallback prompt, built with the model from the factory kwargs.
with_prompt = LangfuseChainFactory(get_client(), model="gpt-5.5", model_provider="openai").create(
    "support-reply",
    fallback=[{"role": "user", "content": "{{question}}"}],
)

# Option 2: a local chain through the LangChain fallback mechanism.
local_chain = ChatPromptTemplate.from_messages([("user", "{question}")]) | init_chat_model(
    "gpt-5.5", model_provider="openai"
)
with_chain = factory.create("support-reply").with_fallbacks([local_chain], exceptions_to_handle=(PromptFetchError,))

print(with_prompt.invoke(question).content)
print(with_chain.invoke(question).content)
