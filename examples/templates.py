"""
Render the prompt with jinja2 instead of the Langfuse substitution rules: ``pip install "langfuse-hotswap[jinja2]"``.
"""

from langchain_openai import ChatOpenAI
from langfuse import get_client

from langfuse_hotswap import LangfuseChainFactory

# The default for prompts whose config has no "template_format" key.
factory = LangfuseChainFactory(get_client(), models={"openai": ChatOpenAI(model="gpt-5.5")}, template_format="jinja2")

# The prompt in Langfuse: "Reply in {{ language | upper }}.{% if urgent %} Be brief.{% endif %} {{ question }}"
# A single prompt can pick its own format with {"template_format": "mustache"} in its config.
chain = factory.create("support-reply-jinja")

message = chain.invoke({"language": "English", "urgent": True, "question": "How do I reset my password?"})
print(message.content)
