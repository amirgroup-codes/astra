"""
SynthesisNetworkAgent: Generates complete bipartite synthesis networks.

This agent replaces the step-by-step synthesis approach with a single-call
network generation that produces the entire synthesis pathway at once.
"""
import json
from typing import List, Optional, TYPE_CHECKING
from autogen_core.models import UserMessage, SystemMessage

from config.azure_config import get_high_reasoning_client
from config.prompts import SYNTHESIS_NETWORK_AGENT_PROMPT, get_synthesis_network_prompt
from models.pathway_schemas import SynthesisNetwork

if TYPE_CHECKING:
    from core.io_logger import IOLogger


class SynthesisNetworkAgent:
    """
    Agent that generates complete bipartite synthesis networks in a single call.

    Unlike step-by-step synthesis agents, this agent produces the entire
    network of molecules and reactions at once, including:
    - All molecule nodes (starting, intermediate, hub, target)
    - All reaction nodes connecting molecules
    - Multiple pathways through the network
    - Hub molecules and convergence points
    """

    def __init__(self, io_logger: Optional["IOLogger"] = None):
        """Initialize the SynthesisNetworkAgent with high-reasoning client."""
        self.client = get_high_reasoning_client()
        self.system_prompt = SYNTHESIS_NETWORK_AGENT_PROMPT
        self.io_logger = io_logger

    async def generate_synthesis_network(
        self,
        target_molecule: str,
        num_pathways: int = 3,
        failed_attempts: Optional[List[dict]] = None,
        deep_research_findings: Optional[str] = None
    ) -> SynthesisNetwork:
        """
        Generate a complete synthesis network for the target molecule.

        Args:
            target_molecule: The target molecule to synthesize
            num_pathways: Number of alternative pathways to generate
            failed_attempts: Previous failed attempts with feedback for learning

        Returns:
            SynthesisNetwork: Complete bipartite synthesis network
        """
        # Generate context-specific prompt
        user_prompt = get_synthesis_network_prompt(
            target_molecule=target_molecule,
            num_pathways=num_pathways,
            failed_attempts=failed_attempts,
            deep_research_findings=deep_research_findings
        )

        try:
            messages = [
                SystemMessage(content=self.system_prompt),
                UserMessage(content=user_prompt, source="user")
            ]

            # Log if logger available
            if self.io_logger:
                from core.io_logger import log_llm_call
                async with log_llm_call(
                    self.io_logger,
                    agent_name="SynthesisNetworkAgent",
                    method_name="generate_synthesis_network",
                    system_message=self.system_prompt,
                    user_message=user_prompt
                ) as interaction:
                    response = await self.client.create(
                        messages=messages,
                        json_output=True,
                        extra_create_args={"response_format": {"type": "json_object"}}
                    )
                    content = response.content
                    interaction.raw_response = content if isinstance(content, str) else json.dumps(content)
                    if hasattr(response, 'reasoning') and response.reasoning:
                        interaction.reasoning = response.reasoning

                    if isinstance(content, str):
                        network_data = json.loads(content)
                    else:
                        network_data = content
                    interaction.parsed_response = network_data
            else:
                response = await self.client.create(
                    messages=messages,
                    json_output=True,
                    extra_create_args={"response_format": {"type": "json_object"}}
                )
                content = response.content
                if isinstance(content, str):
                    network_data = json.loads(content)
                else:
                    network_data = content

            # Validate and create SynthesisNetwork
            network = SynthesisNetwork(**network_data)
            return network

        except Exception as e:
            raise RuntimeError(f"Failed to generate synthesis network: {str(e)}")

