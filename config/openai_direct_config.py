"""
Direct OpenAI API configuration and client setup for GPT-5.4.
Uses OpenAI's API directly (not Azure).
"""
import os
import asyncio
import functools
import logging
from typing import List, Optional, Any
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv("config.env")

logger = logging.getLogger(__name__)


class OpenAIDirectClientWrapper:
    """
    Wrapper for direct OpenAI Responses API that mimics the high-reasoning client interface.

    Uses OpenAI's API directly instead of Azure, with the same
    responses.create() endpoint and reasoning parameters.
    """

    DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes

    def __init__(self, timeout_seconds: int = None):
        """Initialize the direct OpenAI client.

        Args:
            timeout_seconds: Timeout for API calls in seconds (default: 600 = 10 minutes)
        """
        api_key = os.getenv("OPENAI_DIRECT_API_KEY")

        if not api_key:
            raise ValueError(
                "Missing OPENAI_DIRECT_API_KEY environment variable. "
                "Please check config.env contains:\n"
                "- OPENAI_DIRECT_API_KEY"
            )

        self.timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        self.model = os.getenv("OPENAI_DIRECT_MODEL", "gpt-5.4")

        import httpx
        timeout_config = httpx.Timeout(
            connect=30.0,
            read=self.timeout,
            write=30.0,
            pool=30.0
        )

        self.client = OpenAI(
            api_key=api_key,
            timeout=timeout_config,
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

    def _call_api(self, input_text: str):
        """Synchronous API call for use with run_in_executor.

        This call may take several minutes for high-reasoning models.
        The timeout is configured in __init__ (default 10 minutes).
        """
        logger.info(f"OpenAIDirectClientWrapper: Starting API call (model={self.model}, timeout={self.timeout}s)...")

        try:
            result = self.client.responses.create(
                model=self.model,
                input=input_text,
                reasoning={"effort": "low"},
                text={"verbosity": "medium"},
            )
            logger.info("OpenAIDirectClientWrapper: API call completed successfully")
            return result
        except Exception as e:
            logger.error(f"OpenAIDirectClientWrapper: API call failed: {type(e).__name__}: {str(e)}")
            raise

    async def create(
        self,
        messages: List[Any],
        json_output: bool = False,
        extra_create_args: Optional[dict] = None
    ):
        """
        Create a completion using direct OpenAI responses API with reasoning.

        Args:
            messages: List of SystemMessage/UserMessage objects
            json_output: Whether to request JSON output
            extra_create_args: Additional arguments (for compatibility)

        Returns:
            GPT5Response: Response with .content attribute
        """
        from config.azure_config import GPT5Response

        input_text = self._messages_to_input(messages)

        if json_output:
            input_text += "\n\n[OUTPUT FORMAT]\nYou must respond with valid JSON only. No markdown, no explanation, just the JSON object."

        logger.info("OpenAIDirectClientWrapper.create: Awaiting API call (this may take several minutes)...")

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                functools.partial(self._call_api, input_text)
            )

            output_text = result.output_text if hasattr(result, 'output_text') else str(result)

            logger.info(f"OpenAIDirectClientWrapper.create: Response received ({len(output_text)} chars)")
            logger.info("Rate limit delay: waiting 180 seconds...")
            await asyncio.sleep(180)
            return GPT5Response(content=output_text)

        except Exception as e:
            logger.error(f"OpenAIDirectClientWrapper.create: Failed with {type(e).__name__}: {str(e)}")
            raise
