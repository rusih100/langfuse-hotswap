"""
The same chain from asyncio.
"""

import asyncio

from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

factory = LangfuseChainFactory(get_client())
chain = factory.create("support-reply")

question = {"product": "Acme Mail", "language": "English", "question": "How do I reset my password?"}


async def main() -> None:
    """
    Warms the chain up, then calls it.
    """

    # Optional: fetch the prompt and build the chain off the event loop before the first request.
    await asyncio.to_thread(chain.get_input_schema)

    message = await chain.ainvoke(question)
    print(message.content)

    async for chunk in chain.astream(question):
        print(chunk.content, end="", flush=True)
    print()

    replies = await asyncio.gather(*(chain.ainvoke(question) for _ in range(4)))
    print(len(replies), "replies")


asyncio.run(main())
