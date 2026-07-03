"""
GPT-5.4 Azure Agent configuration and client wrapper.

Provides a GPT54AgentAzureClientWrapper that uses Azure AI Projects SDK
with agent references, enabling the system to query a pre-configured
Azure AI agent instead of calling a model directly.

Uses DefaultAzureCredential for authentication (no API key needed)
and the AIProjectClient to get an OpenAI client with agent_reference support.

Requirements:
    pip install azure-ai-projects>=2.0.0 azure-identity
"""
import os
import asyncio
import functools
import logging
from typing import List, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv("config.env")

logger = logging.getLogger(__name__)


class GPT54AgentAzureClientWrapper:
    """
    Wrapper for Azure AI Agent that mimics the high-reasoning client interface.

    Uses AIProjectClient with DefaultAzureCredential to authenticate,
    then calls the responses API with an agent_reference in extra_body.
    """

    DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes

    def __init__(self, timeout_seconds: int = None):
        """Initialize the Azure AI Agent client.

        Args:
            timeout_seconds: Timeout for API calls in seconds (default: 600 = 10 minutes)
        """
        from azure.identity import DefaultAzureCredential
        from azure.ai.projects import AIProjectClient

        endpoint = os.getenv("AZURE_AGENT_PROJECT_ENDPOINT")
        self.agent_name = os.getenv("AZURE_AGENT_NAME")
        self.agent_version = os.getenv("AZURE_AGENT_VERSION", "1")

        if not all([endpoint, self.agent_name]):
            raise ValueError(
                "Missing Azure Agent environment variables. Please check config.env contains:\n"
                "- AZURE_AGENT_PROJECT_ENDPOINT\n"
                "- AZURE_AGENT_NAME\n"
                "- AZURE_AGENT_VERSION (optional, defaults to '1')"
            )

        self.timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS

        project_client = AIProjectClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )

        self.client = project_client.get_openai_client()

        logger.info(
            f"GPT54AgentAzureClientWrapper: Initialized with agent={self.agent_name}, "
            f"version={self.agent_version}, endpoint={endpoint}"
        )

    def _messages_to_input(self, messages: List[Any]) -> str:
        """
        Convert AutoGen message objects to a single input string for the responses API.

        Args:
            messages: List of SystemMessage/UserMessage objects

        Returns:
            str: Combined input string
        """
        parts = []
        for msg in messages:
            if hasattr(msg, 'content'):
                content = msg.content
                msg_type = type(msg).__name__
                if 'System' in msg_type:
                    parts.append(f"[SYSTEM INSTRUCTIONS]\n{content}")
                else:
                    parts.append(f"[USER REQUEST]\n{content}")
        return "\n\n".join(parts)

    def _clean_json_response(self, text: str) -> str:
        """Strip markdown code fences from JSON responses."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _call_api(self, input_text: str):
        """Synchronous API call for use with run_in_executor."""
        logger.info(
            f"GPT54AgentAzureClientWrapper: Starting API call "
            f"(agent={self.agent_name}, version={self.agent_version}, "
            f"timeout={self.timeout}s)..."
        )

        try:
            result = self.client.responses.create(
                input=[{"role": "user", "content": input_text}],
                extra_body={
                    "agent_reference": {
                        "name": self.agent_name,
                        "version": self.agent_version,
                        "type": "agent_reference",
                    }
                },
            )
            logger.info("GPT54AgentAzureClientWrapper: API call completed successfully")
            return result
        except Exception as e:
            logger.error(
                f"GPT54AgentAzureClientWrapper: API call failed: "
                f"{type(e).__name__}: {str(e)}"
            )
            raise

    async def create(
        self,
        messages: List[Any],
        json_output: bool = False,
        extra_create_args: Optional[dict] = None
    ):
        """
        Create a completion using Azure AI Agent via the responses API.

        Interface matches the high-reasoning client create() exactly.

        Args:
            messages: List of SystemMessage/UserMessage objects
            json_output: Whether to request JSON output
            extra_create_args: Additional arguments (accepted for interface compat, ignored)

        Returns:
            GPT5Response: Response with .content and .reasoning attributes
        """
        from config.azure_config import GPT5Response

        input_text = self._messages_to_input(messages)

        if json_output:
            input_text += (
                "\n\n[OUTPUT FORMAT]\n"
                "You must respond with valid JSON only. "
                "No markdown, no explanation, just the JSON object."
            )

        logger.info(
            "GPT54AgentAzureClientWrapper.create: Awaiting agent API call "
            "(this may take several minutes)..."
        )

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                functools.partial(self._call_api, input_text)
            )

            output_text = result.output_text if hasattr(result, 'output_text') else str(result)

            if json_output:
                output_text = self._clean_json_response(output_text)

            logger.info(
                f"GPT54AgentAzureClientWrapper.create: Response received "
                f"({len(output_text)} chars)"
            )

            logger.info("Rate limit delay: waiting 10 seconds...")
            await asyncio.sleep(10)

            return GPT5Response(content=output_text)

        except Exception as e:
            logger.error(
                f"GPT54AgentAzureClientWrapper.create: Failed with "
                f"{type(e).__name__}: {str(e)}"
            )
            raise
