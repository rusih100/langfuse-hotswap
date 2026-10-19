"""
Parse the reply into a Pydantic model.
"""

from langfuse import get_client
from pydantic import BaseModel

from langfuse_hotswap import LangfuseChainFactory


class Reply(BaseModel):
    """
    A support reply with an escalation flag.
    """

    text: str
    escalate_to_human: bool


factory = LangfuseChainFactory(get_client())
chain = factory.create("support-reply").with_structured_output(Reply)

reply = chain.invoke({"product": "Acme Mail", "language": "English", "question": "I was charged twice."})
print(reply.text)
print("escalate:", reply.escalate_to_human)
