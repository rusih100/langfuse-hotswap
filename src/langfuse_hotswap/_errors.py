"""
Exceptions of the package.
"""


class HotswapError(Exception):
    """
    Base error of the package.
    """


class PromptFetchError(HotswapError):
    """
    Raised when the prompt could not be fetched from Langfuse.
    """


class ChainBuildError(HotswapError):
    """
    Raised when the chain could not be built from the fetched prompt.
    """
