"""
AstroDeepResearchAgent: Conducts deep research on proposed chemical reactions.

Uses the o3-deep-research model via Azure AI Services to analyze reaction
feasibility with literature citations.
"""
import asyncio
import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from config.deep_research_config import get_deep_research_client, get_deep_research_model
from config.prompts import DEEP_RESEARCH_AGENT_PROMPT
from models.schemas import ReactionStep, DeepResearchReport, Citation
from models.pathway_schemas import SynthesisNetwork, SynthesisPathway

if TYPE_CHECKING:
    from core.io_logger import IOLogger


class AstroDeepResearchAgent:
    """
    Agent that conducts deep scientific research on proposed chemical reactions.
    Uses the o3-deep-research model for web-based literature search.
    """

    def __init__(self, io_logger: Optional["IOLogger"] = None):
        """
        Initialize the AstroDeepResearchAgent.
        """
        self.client = get_deep_research_client()
        self.model = get_deep_research_model()
        self.system_prompt = DEEP_RESEARCH_AGENT_PROMPT
        self.io_logger = io_logger

    def _reaction_to_query(self, reaction: ReactionStep) -> str:
        """
        Convert a ReactionStep to a natural language research query.

        Args:
            reaction: The proposed reaction to research

        Returns:
            str: Natural language query for the research model
        """
        # Build readable reactants string
        reactants_str = ", ".join([
            f"{r.formula} ({r.common_name or r.iupac_name})"
            for r in reaction.reactants
        ])

        # Build product string
        product_str = f"{reaction.product.formula} ({reaction.product.common_name or reaction.product.iupac_name})"

        # Get environment details
        env = reaction.conditions.get("environment", "unknown")
        temp = reaction.conditions.get("temperature", "unknown")
        pressure = reaction.conditions.get("pressure", "unknown")

        query = f"""Research the following proposed chemical reaction in the context of {env} chemistry:

Reaction: {reaction.reaction}
Reactants: {reactants_str}
Product: {product_str}
Environment: {env}
Temperature: {temp}
Pressure: {pressure}

Proposed reasoning by synthesis agent: {reaction.reasoning}

Please investigate and provide:
1. Is this reaction chemically feasible? Has it been observed or documented?
2. What are the known mechanisms and kinetics for this or similar reactions?
3. What environmental conditions are required for this reaction?
4. Are there peer-reviewed studies supporting or contradicting this pathway?
5. What is your overall scientific assessment of this reaction's plausibility?

Focus on astrochemistry, prebiotic chemistry, and origin of life literature."""

        return query

    def _target_molecule_to_query(self, target_molecule: str) -> str:
        """
        Build a comprehensive research query for a target molecule's prebiotic synthesis.

        Args:
            target_molecule: Name of the target molecule

        Returns:
            str: Natural language query for the research model
        """
        query = f"""Conduct comprehensive research on the prebiotic synthesis of {target_molecule}.

Please investigate and provide detailed information on:

1. KNOWN PREBIOTIC SYNTHESIS ROUTES for {target_molecule}:
   - What pathways have been proposed or demonstrated in the literature?
   - Which routes start from simple molecules (H2O, CO2, NH3, HCN, H2CO, H2S, CH4, H2)?
   - What are the key reaction steps in each route?

2. KEY INTERMEDIATES on the path to {target_molecule}:
   - What are the essential precursor molecules?
   - Which intermediates serve as branch points for multiple pathways?

3. ENVIRONMENTAL CONDITIONS for synthesis:
   - Hydrothermal vent conditions (temperature, pressure, mineral catalysts)
   - Surface/evaporitic pool conditions (wet-dry cycles, UV, mineral surfaces)
   - Which environment is most favorable for each step?

4. MINERAL CATALYSTS relevant to {target_molecule} synthesis:
   - Iron-sulfur minerals (greigite, pyrite, magnetite)
   - Clay minerals (montmorillonite)
   - Other relevant catalysts

5. EXPERIMENTAL EVIDENCE:
   - Key laboratory experiments demonstrating relevant reactions
   - Yields, selectivities, and conditions from published studies
   - Miller-Urey type experiments, hydrothermal vent simulations

6. OPEN QUESTIONS AND CHALLENGES:
   - What steps remain unresolved or debated?
   - What are the main bottlenecks in prebiotic synthesis of {target_molecule}?

Focus on astrochemistry, prebiotic chemistry, and origin of life literature.
Provide specific citations with author names, years, and journal names."""

        return query

    async def research_target_molecule(self, target_molecule: str) -> DeepResearchReport:
        """
        Conduct comprehensive deep research on a target molecule's prebiotic synthesis.

        Unlike research_reaction() or research_pathway() which research specific proposed
        chemistry, this method researches the target molecule broadly - known synthesis
        routes, key intermediates, experimental evidence, and open questions.

        Args:
            target_molecule: Name of the target molecule to research

        Returns:
            DeepResearchReport: Comprehensive research findings with citations
        """
        query = self._target_molecule_to_query(target_molecule)
        start_time = time.time()

        try:
            import logging
            logger = logging.getLogger(__name__)

            loop = asyncio.get_event_loop()

            # Use the target-molecule-specific system prompt
            from config.prompts import DEEP_RESEARCH_TARGET_MOLECULE_PROMPT
            system_prompt = DEEP_RESEARCH_TARGET_MOLECULE_PROMPT

            def _call_api():
                logger.info(
                    f"AstroDeepResearchAgent: Starting target molecule research for "
                    f"'{target_molecule}' (this may take several minutes)..."
                )
                try:
                    result = self.client.responses.create(
                        model=self.model,
                        input=[
                            {
                                "role": "developer",
                                "content": [{"type": "input_text", "text": system_prompt}]
                            },
                            {
                                "role": "user",
                                "content": [{"type": "input_text", "text": query}]
                            }
                        ],
                        reasoning={"summary": "auto"},
                        tools=[{"type": "web_search_preview"}]
                    )
                    logger.info("AstroDeepResearchAgent: Target molecule research completed")
                    return result
                except Exception as e:
                    logger.error(f"AstroDeepResearchAgent: Target molecule research failed: {e}")
                    raise

            response = await loop.run_in_executor(None, _call_api)
            logger.info("Rate limit delay: waiting 180 seconds...")
            await asyncio.sleep(180)
            report = self._parse_response(response, query)

            # Log if logger available
            if self.io_logger:
                duration_ms = (time.time() - start_time) * 1000
                from core.io_logger import LLMInteraction
                interaction = LLMInteraction(
                    timestamp=datetime.now().isoformat(),
                    agent_name="AstroDeepResearchAgent",
                    method_name="research_target_molecule",
                    step=self.io_logger._current_step,
                    attempt=self.io_logger._current_attempt,
                    system_message=system_prompt,
                    user_message=query,
                    raw_response=report.findings if report.findings else "",
                    parsed_response={
                        "target_molecule": target_molecule,
                        "research_successful": report.research_successful,
                        "citations_count": len(report.citations)
                    },
                    duration_ms=duration_ms,
                    success=report.research_successful,
                    error_message=report.error_message
                )
                self.io_logger.log_interaction(interaction)

            return report

        except Exception as e:
            if self.io_logger:
                duration_ms = (time.time() - start_time) * 1000
                from core.io_logger import LLMInteraction
                interaction = LLMInteraction(
                    timestamp=datetime.now().isoformat(),
                    agent_name="AstroDeepResearchAgent",
                    method_name="research_target_molecule",
                    step=self.io_logger._current_step,
                    attempt=self.io_logger._current_attempt,
                    system_message=DEEP_RESEARCH_TARGET_MOLECULE_PROMPT,
                    user_message=query,
                    raw_response="",
                    parsed_response=None,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=str(e)
                )
                self.io_logger.log_interaction(interaction)

            return DeepResearchReport(
                query=query,
                findings="",
                citations=[],
                research_successful=False,
                error_message=str(e)
            )

    async def research_reaction(self, reaction: ReactionStep) -> DeepResearchReport:
        """
        Conduct deep research on a proposed reaction.

        Args:
            reaction: The proposed ReactionStep to research

        Returns:
            DeepResearchReport: Research findings with citations
        """
        query = self._reaction_to_query(reaction)
        start_time = time.time()

        try:
            # Run the synchronous API call in a thread pool
            # Timeout is configured in get_deep_research_client() (default 10 minutes)
            import logging
            logger = logging.getLogger(__name__)

            loop = asyncio.get_event_loop()

            def _call_api():
                logger.info("AstroDeepResearchAgent: Starting deep research API call (this may take several minutes)...")
                try:
                    result = self.client.responses.create(
                        model=self.model,
                        input=[
                            {
                                "role": "developer",
                                "content": [{"type": "input_text", "text": self.system_prompt}]
                            },
                            {
                                "role": "user",
                                "content": [{"type": "input_text", "text": query}]
                            }
                        ],
                        reasoning={"summary": "auto"},
                        tools=[{"type": "web_search_preview"}]
                    )
                    logger.info("AstroDeepResearchAgent: API call completed successfully")
                    return result
                except Exception as e:
                    logger.error(f"AstroDeepResearchAgent: API call failed: {type(e).__name__}: {str(e)}")
                    raise

            response = await loop.run_in_executor(None, _call_api)
            logger.info("Rate limit delay: waiting 180 seconds...")
            await asyncio.sleep(180)

            # Parse the response
            report = self._parse_response(response, query)

            # Log if logger available
            if self.io_logger:
                duration_ms = (time.time() - start_time) * 1000
                from core.io_logger import LLMInteraction
                interaction = LLMInteraction(
                    timestamp=datetime.now().isoformat(),
                    agent_name="AstroDeepResearchAgent",
                    method_name="research_reaction",
                    step=self.io_logger._current_step,
                    attempt=self.io_logger._current_attempt,
                    system_message=self.system_prompt,
                    user_message=query,
                    raw_response=report.findings if report.findings else "",
                    parsed_response={
                        "research_successful": report.research_successful,
                        "citations_count": len(report.citations),
                        "findings_length": len(report.findings) if report.findings else 0
                    },
                    duration_ms=duration_ms,
                    success=report.research_successful,
                    error_message=report.error_message
                )
                self.io_logger.log_interaction(interaction)

            return report

        except Exception as e:
            # Log error if logger available
            if self.io_logger:
                duration_ms = (time.time() - start_time) * 1000
                from core.io_logger import LLMInteraction
                interaction = LLMInteraction(
                    timestamp=datetime.now().isoformat(),
                    agent_name="AstroDeepResearchAgent",
                    method_name="research_reaction",
                    step=self.io_logger._current_step,
                    attempt=self.io_logger._current_attempt,
                    system_message=self.system_prompt,
                    user_message=query,
                    raw_response="",
                    parsed_response=None,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=str(e)
                )
                self.io_logger.log_interaction(interaction)

            return DeepResearchReport(
                query=query,
                findings="",
                citations=[],
                research_successful=False,
                error_message=str(e)
            )

    def _parse_response(self, response, query: str) -> DeepResearchReport:
        """
        Parse the API response into a DeepResearchReport.

        Args:
            response: The API response object
            query: The original query

        Returns:
            DeepResearchReport: Parsed research report
        """
        findings = ""
        citations = []

        if response.output:
            # Get the final output (typically the last item)
            final_output = response.output[-1]

            if hasattr(final_output, 'content') and final_output.content:
                findings = final_output.content[0].text

                # Extract citations if available
                if hasattr(final_output.content[0], 'annotations'):
                    annotations = final_output.content[0].annotations
                    if annotations:
                        for annotation in annotations:
                            citations.append(Citation(
                                title=getattr(annotation, 'title', 'Unknown'),
                                url=getattr(annotation, 'url', '')
                            ))

        return DeepResearchReport(
            query=query,
            findings=findings,
            citations=citations,
            research_successful=True,
            error_message=None
        )

    def _pathway_to_query(self, pathway: SynthesisPathway, network: SynthesisNetwork) -> str:
        """
        Convert a SynthesisPathway to a research query.

        Args:
            pathway: The pathway to research
            network: The full network for context

        Returns:
            str: Natural language query for research
        """
        # Get key reactions in this pathway
        reactions_info = []
        for rxn_id in pathway.reaction_sequence[:5]:  # Limit to first 5
            rxn = network.get_reaction(rxn_id)
            if rxn:
                inputs = [network.get_molecule(m) for m in rxn.inputs]
                outputs = [network.get_molecule(m) for m in rxn.outputs]
                input_str = ", ".join([f"{m.formula}" for m in inputs if m])
                output_str = ", ".join([f"{m.formula}" for m in outputs if m])
                reactions_info.append(f"{input_str} -> {output_str} ({rxn.environment})")

        # Get key intermediates
        intermediates_info = []
        for mol_id in pathway.key_intermediates[:3]:
            mol = network.get_molecule(mol_id)
            if mol:
                intermediates_info.append(f"{mol.formula} ({mol.common_name or mol.iupac_name})")

        query = f"""Research the following prebiotic synthesis pathway for {network.target_molecule}:

Pathway: {pathway.name}
Description: {pathway.description}

Key reactions in this pathway:
{chr(10).join(f"- {r}" for r in reactions_info)}

Key intermediates: {', '.join(intermediates_info)}

Please investigate and provide:
1. Is this overall synthesis pathway supported by literature?
2. Are the key reactions chemically feasible under prebiotic conditions?
3. What experimental evidence exists for similar pathways?
4. What are the main challenges or bottlenecks in this pathway?
5. Are there alternative routes documented in the literature?

Focus on astrochemistry, prebiotic chemistry, and origin of life literature."""

        return query

    async def research_pathway(
        self,
        pathway: SynthesisPathway,
        network: SynthesisNetwork
    ) -> DeepResearchReport:
        """
        Conduct deep research on a synthesis pathway.

        Args:
            pathway: The pathway to research
            network: The full network for context

        Returns:
            DeepResearchReport: Research findings with citations
        """
        query = self._pathway_to_query(pathway, network)
        start_time = time.time()

        try:
            import logging
            logger = logging.getLogger(__name__)
            loop = asyncio.get_event_loop()

            def _call_api():
                logger.info(f"AstroDeepResearchAgent: Researching pathway '{pathway.name}'...")
                try:
                    result = self.client.responses.create(
                        model=self.model,
                        input=[
                            {
                                "role": "developer",
                                "content": [{"type": "input_text", "text": self.system_prompt}]
                            },
                            {
                                "role": "user",
                                "content": [{"type": "input_text", "text": query}]
                            }
                        ],
                        reasoning={"summary": "auto"},
                        tools=[{"type": "web_search_preview"}]
                    )
                    logger.info("AstroDeepResearchAgent: Pathway research completed")
                    return result
                except Exception as e:
                    logger.error(f"AstroDeepResearchAgent: Pathway research failed: {e}")
                    raise

            response = await loop.run_in_executor(None, _call_api)
            logger.info("Rate limit delay: waiting 180 seconds...")
            await asyncio.sleep(180)
            report = self._parse_response(response, query)

            # Log if logger available
            if self.io_logger:
                duration_ms = (time.time() - start_time) * 1000
                from core.io_logger import LLMInteraction
                interaction = LLMInteraction(
                    timestamp=datetime.now().isoformat(),
                    agent_name="AstroDeepResearchAgent",
                    method_name="research_pathway",
                    step=self.io_logger._current_step,
                    attempt=self.io_logger._current_attempt,
                    system_message=self.system_prompt,
                    user_message=query,
                    raw_response=report.findings if report.findings else "",
                    parsed_response={
                        "pathway_name": pathway.name,
                        "research_successful": report.research_successful,
                        "citations_count": len(report.citations)
                    },
                    duration_ms=duration_ms,
                    success=report.research_successful,
                    error_message=report.error_message
                )
                self.io_logger.log_interaction(interaction)

            return report

        except Exception as e:
            return DeepResearchReport(
                query=query,
                findings="",
                citations=[],
                research_successful=False,
                error_message=str(e)
            )

    async def research_network(
        self,
        network: SynthesisNetwork,
        focus_pathway_id: str = None
    ) -> dict:
        """
        Research a synthesis network.

        Args:
            network: The synthesis network to research
            focus_pathway_id: Optional specific pathway to focus on

        Returns:
            Dict mapping pathway_id to DeepResearchReport
        """
        results = {}

        if focus_pathway_id:
            # Research only the specified pathway
            pathway = network.get_pathway(focus_pathway_id)
            if pathway:
                results[focus_pathway_id] = await self.research_pathway(pathway, network)
        else:
            # Research all pathways (or at least the primary one)
            for pathway in network.pathways[:2]:  # Limit to first 2 pathways
                results[pathway.pathway_id] = await self.research_pathway(pathway, network)

        return results
