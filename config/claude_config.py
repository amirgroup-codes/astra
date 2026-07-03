"""
Claude Opus 4.6 configuration and client wrapper.

Provides a ClaudeClientWrapper that matches the high-reasoning client interface
(async create() returning a GPT5Response), enabling drop-in replacement for
high-reasoning agents.
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


class ClaudeClientWrapper:
    """
    Wrapper for Claude Opus 4.6 that mimics the high-reasoning client interface.

    Uses the Anthropic Python SDK with optional extended thinking.
    All agents using get_high_reasoning_client() will work transparently.
    """

    DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes (matching GPT-5)

    def __init__(self, timeout_seconds: int = None):
        """Initialize the Claude client with Anthropic credentials.

        Args:
            timeout_seconds: Timeout for API calls in seconds (default: 600 = 10 minutes)
        """
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Missing ANTHROPIC_API_KEY environment variable. "
                "Please set it in config.env."
            )

        self.timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        self.model = os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101")
        self.max_tokens = int(os.getenv("CLAUDE_MAX_TOKENS", "32768"))
        self.thinking_budget = int(os.getenv("CLAUDE_THINKING_BUDGET", "10000"))
        self.enable_thinking = os.getenv("CLAUDE_ENABLE_THINKING", "true").lower() == "true"

        import httpx
        timeout_config = httpx.Timeout(
            connect=30.0,
            read=self.timeout,
            write=30.0,
            pool=30.0
        )

        self.client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout_config,
        )

    def _messages_to_anthropic_format(self, messages: List[Any]) -> tuple:
        """
        Convert AutoGen SystemMessage/UserMessage objects to Anthropic format.

        Args:
            messages: List of SystemMessage/UserMessage objects

        Returns:
            tuple: (system_prompt: str, messages: list of dicts)
        """
        system_prompt = ""
        anthropic_messages = []

        for msg in messages:
            if hasattr(msg, 'content'):
                content = msg.content
                msg_type = type(msg).__name__
                if 'System' in msg_type:
                    system_prompt = content
                else:
                    anthropic_messages.append({
                        "role": "user",
                        "content": content
                    })

        # Ensure at least one user message
        if not anthropic_messages:
            anthropic_messages.append({
                "role": "user",
                "content": system_prompt
            })
            system_prompt = ""

        return system_prompt, anthropic_messages

    # Anthropic requires streaming when max_tokens exceeds this threshold
    STREAMING_THRESHOLD = 21333

    def _call_api(self, system_prompt: str, messages: list, json_output: bool):
        """Synchronous API call for use with run_in_executor.

        This call may take several minutes for extended thinking models.
        The timeout is configured in __init__ (default 10 minutes).

        Uses streaming when max_tokens > 21333 (Anthropic API requirement).
        """
        logger.info(f"ClaudeClientWrapper: Starting API call (model={self.model}, timeout={self.timeout}s)")

        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        # Enable extended thinking if configured
        if self.enable_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }

        try:
            if self.max_tokens > self.STREAMING_THRESHOLD:
                # Streaming required for large max_tokens
                with self.client.messages.stream(**kwargs) as stream:
                    result = stream.get_final_message()
            else:
                result = self.client.messages.create(**kwargs)
            logger.info("ClaudeClientWrapper: API call completed successfully")
            return result
        except Exception as e:
            logger.error(f"ClaudeClientWrapper: API call failed: {type(e).__name__}: {str(e)}")
            raise

    def _extract_text(self, response) -> str:
        """Extract text content from Claude response, skipping thinking blocks."""
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "\n".join(text_parts)

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

    async def create(
        self,
        messages: List[Any],
        json_output: bool = False,
        extra_create_args: Optional[dict] = None
    ):
        """
        Create a completion using Claude Opus 4.6 with optional extended thinking.

        Interface matches the high-reasoning client create() exactly.

        Args:
            messages: List of SystemMessage/UserMessage objects
            json_output: Whether to request JSON output
            extra_create_args: Additional arguments (accepted for interface compat, ignored)

        Returns:
            GPT5Response: Response with .content attribute
        """
        # Import here to avoid circular imports
        from config.azure_config import GPT5Response

        system_prompt, anthropic_messages = self._messages_to_anthropic_format(messages)

        # Add JSON instruction if requested (same pattern as the other high-reasoning wrappers)
        if json_output and anthropic_messages:
            last_msg = anthropic_messages[-1]
            last_msg["content"] += (
                "\n\n[OUTPUT FORMAT]\n"
                "You must respond with valid JSON only. "
                "No markdown, no explanation, just the JSON object."
            )

        logger.info("ClaudeClientWrapper.create: Awaiting API call (this may take several minutes)...")

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                functools.partial(
                    self._call_api, system_prompt, anthropic_messages, json_output
                )
            )

            # Extract text content (skipping thinking blocks)
            output_text = self._extract_text(result)

            # Clean JSON response if needed
            if json_output:
                output_text = self._clean_json_response(output_text)

            logger.info(f"ClaudeClientWrapper.create: Response received ({len(output_text)} chars)")
            logger.info("Rate limit delay: waiting 180 seconds...")
            await asyncio.sleep(180)
            return GPT5Response(content=output_text)

        except Exception as e:
            logger.error(f"ClaudeClientWrapper.create: Failed with {type(e).__name__}: {str(e)}")
            raise
