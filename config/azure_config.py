"""
Azure OpenAI configuration and client setup.
"""
import os
import asyncio
from dataclasses import dataclass
from dotenv import load_dotenv
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

# Load environment variables
load_dotenv("config.env")


@dataclass
class GPT5Response:
    """Response wrapper to match AzureOpenAIChatCompletionClient response format."""
    content: str
    reasoning: str = ""  # Model reasoning/thinking (e.g., DeepSeek R1 <think> blocks)


def get_high_reasoning_client():
    """
    Get client for high-reasoning agents.

    Uses MODEL_PROVIDER env var to select one of the three supported models:
    - "claude": Claude Opus 4.6 via Anthropic API
    - "gpt41": GPT-4.1 via Azure OpenAI
    - "gpt5.4_openai": GPT-5.4 via direct OpenAI Responses API
    - "gpt5.4_agent_azure": GPT-5.4 via Azure AI Projects agent

    Returns:
        ClaudeClientWrapper, OpenAIDirectClientWrapper, GPT54AgentAzureClientWrapper,
        or RateLimitedClientWrapper (GPT-4.1)

    Raises:
        ValueError: If MODEL_PROVIDER is unset or not one of the supported values.
    """
    provider = os.getenv("MODEL_PROVIDER", "").lower()

    if provider == "claude":
        from config.claude_config import ClaudeClientWrapper
        return ClaudeClientWrapper()
    elif provider == "gpt41":
        return get_gpt41_client()
    elif provider == "gpt5.4_openai":
        from config.openai_direct_config import OpenAIDirectClientWrapper
        return OpenAIDirectClientWrapper()
    elif provider == "gpt5.4_agent_azure":
        from config.gpt54_agent_azure_config import GPT54AgentAzureClientWrapper
        return GPT54AgentAzureClientWrapper()
    else:
        raise ValueError(
            f"Unsupported MODEL_PROVIDER: {provider!r}. "
            "Set MODEL_PROVIDER in config.env to one of: "
            "'claude', 'gpt41', 'gpt5.4_openai', 'gpt5.4_agent_azure'."
        )


class RateLimitedClientWrapper:
    """Wraps any client and adds a 180-second delay after create() calls."""

    def __init__(self, client):
        self._client = client

    async def create(self, *args, **kwargs):
        import logging
        logger = logging.getLogger(__name__)
        result = await self._client.create(*args, **kwargs)
        logger.info("Rate limit delay: waiting 180 seconds...")
        await asyncio.sleep(180)
        return result


def get_gpt41_client():
    """
    Create and return an Azure OpenAI client configured for GPT-4.1.

    Returns:
        RateLimitedClientWrapper wrapping AzureOpenAIChatCompletionClient
    """
    endpoint = os.getenv("AZURE_GPT41_ENDPOINT")
    api_key = os.getenv("AZURE_GPT41_API_KEY")
    api_version = os.getenv("AZURE_GPT41_API_VERSION")
    deployment = os.getenv("AZURE_GPT41_DEPLOYMENT_NAME")

    if not all([endpoint, api_key, api_version, deployment]):
        raise ValueError(
            "Missing GPT-4.1 environment variables. Please check config.env contains:\n"
            "- AZURE_GPT41_ENDPOINT\n"
            "- AZURE_GPT41_API_KEY\n"
            "- AZURE_GPT41_API_VERSION\n"
            "- AZURE_GPT41_DEPLOYMENT_NAME"
        )

    client = AzureOpenAIChatCompletionClient(
        azure_deployment=deployment,
        model=deployment,
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=api_key,
    )

    return RateLimitedClientWrapper(client)


def get_azure_client() -> AzureOpenAIChatCompletionClient:
    """
    Create and return an Azure OpenAI client configured for structured output.

    Returns:
        AzureOpenAIChatCompletionClient: Configured client instance
    """
    # Get configuration from environment
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    # Validate required environment variables
    if not all([endpoint, api_key, api_version, deployment]):
        raise ValueError(
            "Missing required environment variables. Please check config.env contains:\n"
            "- AZURE_OPENAI_ENDPOINT\n"
            "- AZURE_OPENAI_API_KEY\n"
            "- AZURE_OPENAI_API_VERSION\n"
            "- AZURE_OPENAI_DEPLOYMENT_NAME"
        )

    # Create and return the client (wrapped with rate limiting)
    client = AzureOpenAIChatCompletionClient(
        azure_deployment=deployment,
        model=deployment,  # Model name same as deployment for Azure
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=api_key,
    )

    return RateLimitedClientWrapper(client)
