"""
Configuration for the AstroDeepResearch agent using o3-deep-research model.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI
import httpx

# Load environment variables
load_dotenv("config.env")

# Deep research with web search can take several minutes
DEFAULT_TIMEOUT_SECONDS = 1800  # 30 minutes


def get_deep_research_client(timeout_seconds: int = None) -> OpenAI:
    """
    Create and return an OpenAI client configured for o3-deep-research.

    Args:
        timeout_seconds: Timeout for API calls in seconds (default: 600 = 10 minutes)

    Returns:
        OpenAI: Configured client instance for deep research API
    """
    endpoint = os.getenv("AZURE_DEEP_RESEARCH_ENDPOINT")
    api_key = os.getenv("AZURE_DEEP_RESEARCH_API_KEY")

    if not all([endpoint, api_key]):
        raise ValueError(
            "Missing required environment variables. Please check config.env contains:\n"
            "- AZURE_DEEP_RESEARCH_ENDPOINT\n"
            "- AZURE_DEEP_RESEARCH_API_KEY"
        )

    timeout = timeout_seconds or DEFAULT_TIMEOUT_SECONDS

    # Configure httpx timeout for long-running deep research calls
    timeout_config = httpx.Timeout(
        connect=30.0,      # Connection timeout
        read=timeout,      # Read timeout (waiting for response)
        write=30.0,        # Write timeout
        pool=30.0          # Pool timeout
    )

    client = OpenAI(
        base_url=endpoint,
        api_key=api_key,
        timeout=timeout_config
    )

    return client


def get_deep_research_model() -> str:
    """
    Get the deep research model name from environment.

    Returns:
        str: Model name (defaults to 'o3-deep-research')
    """
    return os.getenv("AZURE_DEEP_RESEARCH_MODEL", "o3-deep-research")
