"""
Create a chain once and call it.
"""

from langchain_openai import ChatOpenAI
from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

factory = LangfuseChainFactory(get_client(), models={"openai": ChatOpenAI(model="gpt-5.5")})
chain = factory.create("support-reply")

question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}

message = chain.invoke(question)
print(message.content)

for chunk in chain.stream(question):
    print(chunk.content, end="", flush=True)
print()

for reply in chain.batch([question, {**question, "language": "German"}]):
    print(reply.content)
