"""
CriticAgent: Evaluates proposed chemical reactions for feasibility.
"""
import json
from typing import Dict, Optional, TYPE_CHECKING
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
from autogen_core.models import UserMessage, SystemMessage

from config.prompts import CRITIC_AGENT_PROMPT, NETWORK_CRITIC_PROMPT, get_critic_prompt
from config.azure_config import get_high_reasoning_client
from models.schemas import CriticEvaluation, ReactionStep, DeepResearchReport, EnrichedProposal
from models.pathway_schemas import (
    SynthesisNetwork,
    SynthesisPathway,
    PathwayEvaluation,
    NetworkEvaluation,
)

if TYPE_CHECKING:
    from core.io_logger import IOLogger


class CriticAgent:
    """
    Agent that evaluates chemical reactions for feasibility and appropriateness.
    """

    def __init__(self, io_logger: Optional["IOLogger"] = None):
        """Initialize the CriticAgent with high-reasoning client (GPT-5.2 or GPT-4o)."""
        self.client = get_high_reasoning_client()
        self.system_prompt = CRITIC_AGENT_PROMPT
        self.io_logger = io_logger

    async def evaluate_reaction(self, reaction: ReactionStep) -> CriticEvaluation:
        """
        Evaluate a proposed chemical reaction.

        Args:
            reaction: The proposed reaction to evaluate

        Returns:
            CriticEvaluation: Detailed evaluation with scores and feedback
        """
        # Create the agent with system prompt
        agent = AssistantAgent(
            name="CriticAgent",
            model_client=self.client,
            system_message=self.system_prompt,
        )

        # Convert reaction to dict for the prompt
        reaction_dict = reaction.model_dump()

        # Generate evaluation prompt
        user_prompt = get_critic_prompt(reaction_dict)

        try:
            # Create messages for the agent
            messages = [TextMessage(content=user_prompt, source="user")]

            # Get response
            response = await agent.on_messages(messages, CancellationToken())

            # Parse the response
            if hasattr(response, 'chat_message') and hasattr(response.chat_message, 'content'):
                content = response.chat_message.content

                # Try to parse as JSON if it's a string
                if isinstance(content, str):
                    # Check if content is wrapped in markdown code blocks
                    if content.startswith("```json"):
                        content = content.replace("```json", "").replace("```", "").strip()
                    elif content.startswith("```"):
                        content = content.replace("```", "").strip()

                    eval_data = json.loads(content)
                else:
                    eval_data = content

                # Validate and create CriticEvaluation
                evaluation = CriticEvaluation(**eval_data)
                return evaluation

        except Exception as e:
            raise RuntimeError(f"Failed to evaluate reaction: {str(e)}")

    async def evaluate_reaction_with_json_mode(
        self,
        reaction: ReactionStep,
        research_report: Optional[DeepResearchReport] = None,
        enriched_context: Optional[EnrichedProposal] = None
    ) -> CriticEvaluation:
        """
        Alternative method using JSON mode for more reliable structured output.

        Args:
            reaction: The proposed reaction to evaluate
            research_report: Optional deep research report for additional context
            enriched_context: Optional enriched proposal from Socratic/Devil's Advocate challenges

        Returns:
            CriticEvaluation: Detailed evaluation with scores and feedback
        """
        # Convert reaction to dict for the prompt
        reaction_dict = reaction.model_dump()

        # Generate evaluation prompt
        user_prompt = get_critic_prompt(reaction_dict)

        # Add research context if available
        if research_report and research_report.research_successful and research_report.findings:
            user_prompt += self._format_research_context(research_report)

        # Add JSON schema instruction
        user_prompt += """

Please respond with a JSON object matching this schema:
{
    "chemical_feasibility": <float 0.0-1.0>,
    "conditions_appropriateness": <float 0.0-1.0>,
    "temperature_feasibility": <float 0.0-1.0>,
    "pressure_feasibility": <float 0.0-1.0>,
    "overall_confidence": <float 0.0-1.0>,
    "feedback": "<detailed feedback explaining your evaluation>",
    "approved": <boolean, true if overall_confidence >= 0.8>,
    "suggestions": [<list of improvement suggestions if not approved, or null>]
}
"""

        try:
            # Use the client directly with JSON mode
            messages = [
                SystemMessage(content=self.system_prompt),
                UserMessage(content=user_prompt, source="user")
            ]

            # Log if logger available
            if self.io_logger:
                from core.io_logger import log_llm_call
                async with log_llm_call(
                    self.io_logger,
                    agent_name="CriticAgent",
                    method_name="evaluate_reaction_with_json_mode",
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
                        eval_data = json.loads(content)
                    else:
                        eval_data = content
                    interaction.parsed_response = eval_data
            else:
                response = await self.client.create(
                    messages=messages,
                    json_output=True,
                    extra_create_args={"response_format": {"type": "json_object"}}
                )
                content = response.content
                if isinstance(content, str):
                    eval_data = json.loads(content)
                else:
                    eval_data = content

            # Validate and create CriticEvaluation
            evaluation = CriticEvaluation(**eval_data)
            return evaluation

        except Exception as e:
            raise RuntimeError(f"Failed to evaluate reaction with JSON mode: {str(e)}")

    def _format_research_context(self, research_report: DeepResearchReport) -> str:
        """
        Format a research report as context for the evaluation prompt.

        Args:
            research_report: The deep research report to format

        Returns:
            str: Formatted research context string
        """
        findings_text = research_report.findings

        # Format citations (up to 10)
        citations_text = ""
        for i, citation in enumerate(research_report.citations, 1):
            citations_text += f"{i}. {citation.title}\n   URL: {citation.url}\n"

        context = f"""

=== DEEP RESEARCH FINDINGS ===
The following research report provides scientific evidence for your evaluation:

{findings_text}

Citations ({len(research_report.citations)} sources found):
{citations_text if citations_text else "No citations available."}

Use this research to inform your evaluation, particularly for:
- Chemical feasibility: Does literature support this reaction?
- Conditions appropriateness: Are the proposed conditions documented?
- Overall confidence: Weight peer-reviewed evidence in your assessment.
===============================
"""
        return context

    async def evaluate_network(
        self,
        network: SynthesisNetwork,
        research_reports: Optional[dict] = None,
        deep_research_report: Optional[DeepResearchReport] = None,
    ) -> NetworkEvaluation:
        """
        Evaluate a complete synthesis network.

        Args:
            network: The synthesis network to evaluate
            research_reports: Optional dict mapping pathway_id to DeepResearchReport

        Returns:
            NetworkEvaluation: Complete network evaluation
        """
        # Build network summary for evaluation
        mol_summary = "\n".join([
            f"  - {m.id}: {m.formula} ({m.common_name or m.iupac_name}) [{m.role}]"
            for m in network.molecules
        ])
        rxn_summary = "\n".join([
            f"  - {r.id}: {', '.join(r.inputs)} -> {', '.join(r.outputs)} ({r.name}) [{r.environment}]"
            for r in network.reactions
        ])
        pathway_summary = "\n".join([
            f"  - {p.pathway_id}: {p.name} ({len(p.reaction_sequence)} steps)"
            for p in network.pathways
        ])

        user_prompt = f"""Evaluate this synthesis network:

TARGET MOLECULE: {network.target_molecule}
OVERALL STRATEGY: {network.overall_strategy}

MOLECULES ({len(network.molecules)} nodes):
{mol_summary}

REACTIONS ({len(network.reactions)} nodes):
{rxn_summary}

PATHWAYS ({len(network.pathways)}):
{pathway_summary}

HUB MOLECULES: {', '.join(network.hub_molecules) if network.hub_molecules else 'None'}
CONVERGENCE POINTS: {len(network.convergence_points)}
"""

        # Add upfront deep research context if available
        if deep_research_report and deep_research_report.research_successful and deep_research_report.findings:
            user_prompt += "\n\n=== LITERATURE RESEARCH ON TARGET MOLECULE ===\n"
            user_prompt += "The following research was conducted on the target molecule before "
            user_prompt += "network generation. Use it to assess whether the network aligns "
            user_prompt += "with known prebiotic chemistry literature.\n\n"
            user_prompt += deep_research_report.findings
            if deep_research_report.citations:
                user_prompt += f"\n\nCitations ({len(deep_research_report.citations)} sources):\n"
                for i, citation in enumerate(deep_research_report.citations, 1):
                    user_prompt += f"  {i}. {citation.title} - {citation.url}\n"
            user_prompt += "\n=== END LITERATURE RESEARCH ===\n"
            user_prompt += "\nConsider how well the network aligns with this literature in your evaluation.\n"

        # Add per-pathway research context if available
        if research_reports:
            user_prompt += "\n\n=== DEEP RESEARCH FINDINGS ===\n"
            for pathway_id, report in research_reports.items():
                if report.research_successful:
                    user_prompt += f"\nPathway {pathway_id}:\n{report.findings}\n"

        user_prompt += """

Please evaluate the network and respond with JSON:
{
    "pathway_evaluations": [
        {
            "pathway_id": "<id>",
            "reaction_scores": {"rxn_001": 0.85, ...},
            "chemical_feasibility": <0.0-1.0>,
            "pathway_coherence": <0.0-1.0>,
            "environmental_progression": <0.0-1.0>,
            "target_achievement": <0.0-1.0>,
            "overall_confidence": <0.0-1.0>,
            "feedback": "<pathway-specific feedback>",
            "approved": <true if confidence >= 0.8>,
            "problematic_reactions": ["rxn_ids with issues"],
            "suggestions": ["improvements"]
        }
    ],
    "best_pathway_id": "<id of best pathway>",
    "overall_confidence": <0.0-1.0>,
    "network_feedback": "<overall assessment>",
    "hub_quality": <0.0-1.0>,
    "convergence_quality": <0.0-1.0>
}
"""

        try:
            messages = [
                SystemMessage(content=NETWORK_CRITIC_PROMPT),
                UserMessage(content=user_prompt, source="user")
            ]

            if self.io_logger:
                from core.io_logger import log_llm_call
                async with log_llm_call(
                    self.io_logger,
                    agent_name="CriticAgent",
                    method_name="evaluate_network",
                    system_message=NETWORK_CRITIC_PROMPT,
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
                        eval_data = json.loads(content)
                    else:
                        eval_data = content
                    interaction.parsed_response = eval_data
            else:
                response = await self.client.create(
                    messages=messages,
                    json_output=True,
                    extra_create_args={"response_format": {"type": "json_object"}}
                )
                content = response.content
                if isinstance(content, str):
                    eval_data = json.loads(content)
                else:
                    eval_data = content

            # Parse pathway evaluations
            pathway_evals = []
            for pe_data in eval_data.get("pathway_evaluations", []):
                pathway_evals.append(PathwayEvaluation(**pe_data))

            # Build NetworkEvaluation
            evaluation = NetworkEvaluation(
                target_molecule=network.target_molecule,
                pathway_evaluations=pathway_evals,
                best_pathway_id=eval_data.get("best_pathway_id", network.pathways[0].pathway_id if network.pathways else ""),
                overall_confidence=eval_data.get("overall_confidence", 0.0),
                network_feedback=eval_data.get("network_feedback", ""),
                approved=eval_data.get("approved", False),
                hub_quality=eval_data.get("hub_quality", 0.0),
                convergence_quality=eval_data.get("convergence_quality", 0.0)
            )

            return evaluation

        except Exception as e:
            raise RuntimeError(f"Failed to evaluate network: {str(e)}")
