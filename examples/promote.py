"""
Move the ``production`` label to a prompt version from code: ``python examples/promote.py 13``.
"""

import sys

from langfuse import get_client

version = int(sys.argv[1])
prompt = get_client().update_prompt(name="support-reply", version=version, new_labels=["production"])
print(f"production -> v{prompt.version}: {prompt.config.get('provider')} / {prompt.config.get('model')}")
