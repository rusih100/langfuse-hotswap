"""
Keep answering when Langfuse is unreachable on a cold start.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory, PromptFetchError

model = ChatOpenAI(model="gpt-5.5")
factory = LangfuseChainFactory(get_client(), models={"openai": model})
question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}

# Once a chain is built it keeps serving through outages and broken versions on its own.
# A fallback is for the cold start, when there is no chain yet: a local chain through the LangChain mechanism.
local_chain = ChatPromptTemplate.from_messages([("user", "{question}")]) | model
chain = factory.create("support-reply").with_fallbacks([local_chain], exceptions_to_handle=(PromptFetchError,))

print(chain.invoke(question).content)
