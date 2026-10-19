"""
Bind tools to the model.
"""

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory


@tool
def open_ticket(summary: str) -> str:
    """
    Opens a support ticket and returns its id.
    """

    return "TICKET-42"


factory = LangfuseChainFactory(get_client())
chain = factory.create("support-reply").bind_tools([open_ticket])

message = chain.invoke({"product": "Acme Mail", "language": "English", "question": "I was charged twice."})
if isinstance(message, AIMessage):
    for call in message.tool_calls:
        print(call["name"], call["args"])
