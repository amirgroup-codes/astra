"""
Network Synthesis Workflow: Simplified workflow using SynthesisNetworkAgent.

Generates complete synthesis networks in a single call, then validates through:
1. Deep Research (optional)
2. Critic evaluation
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from agents.synthesis_network_agent import SynthesisNetworkAgent
from agents.deep_research_agent import AstroDeepResearchAgent
from agents.critic_agent import CriticAgent
from core.io_logger import IOLogger, log_research_content
from models.pathway_schemas import (
    SynthesisNetwork,
    NetworkEvaluation,
    NetworkSynthesisResult
)
from models.schemas import DeepResearchReport, Citation

logger = logging.getLogger(__name__)

MAX_LLM_RETRIES = 10  # Max retries for transient LLM failures within a single attempt


def _normalize_name(name: str) -> str:
    """Normalize a filename by lowercasing and treating hyphens/underscores as equivalent."""
    return name.lower().replace("-", "_")


def _find_file_case_insensitive(directory: str, filename: str) -> Optional[str]:
    """Find a file in a directory with case-insensitive matching.

    Also treats hyphens and underscores as equivalent (e.g., L-Alanine matches L_Alanine).
    Returns the full path if found, None otherwise.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return None

    target_norm = _normalize_name(filename)
    for f in dir_path.iterdir():
        if _normalize_name(f.name) == target_norm:
            return str(f)
    return None


def _load_cached_deep_research(file_path: str) -> DeepResearchReport:
    """Load a DeepResearchReport from a cached file.

    Auto-detects format:
    - JSONL (o3-deep-research): Parses first JSON line, extracts raw_response/user_message.
    - Plain text (Claude, Gemini, ChatGPT): Treats entire file as findings.

    Skips comment lines (starting with #) in JSONL mode.
    Parses markdown URLs into Citation objects.
    """
    with open(file_path, "r") as f:
        content = f.read()

    if not content.strip():
        return DeepResearchReport(
            query="Deep research",
            findings="",
            citations=[],
            research_successful=False,
            error_message="Empty deep research cache file",
        )

    # Try JSONL format first: find first non-empty, non-comment line and try JSON parse
    findings = None
    query = "Deep research"
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            record = json.loads(line)
            # Successfully parsed as JSONL
            success = record.get("success", True)
            raw_response = record.get("raw_response", "")
            if not success or not raw_response:
                return DeepResearchReport(
                    query=record.get("user_message", ""),
                    findings="",
                    citations=[],
                    research_successful=False,
                    error_message=record.get("error_message", "No findings available"),
                )
            findings = raw_response
            query = record.get("user_message", query)
        except (json.JSONDecodeError, ValueError):
            # Not JSONL — treat entire file as plain text findings
            findings = content
        break

    if findings is None:
        findings = content

    # Extract markdown links as citations: [title](url)
    seen_urls = set()
    citations = []
    for title, url in re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', findings):
        if url not in seen_urls:
            seen_urls.add(url)
            citations.append(Citation(title=title, url=url))

    return DeepResearchReport(
        query=query,
        findings=findings,
        citations=citations,
        research_successful=True,
        error_message=None,
    )


def _load_cached_perfect_rag(file_path: str) -> DeepResearchReport:
    """Load perfect RAG findings from a cached markdown file.

    The perfect RAG output is a curated markdown literature review.
    Wraps the content into a DeepResearchReport for use by agents.
    """
    with open(file_path, "r") as f:
        content = f.read()

    if not content.strip():
        return DeepResearchReport(
            query="Perfect RAG literature review",
            findings="",
            citations=[],
            research_successful=False,
            error_message="Empty perfect RAG file",
        )

    # Extract markdown links as citations: [title](url)
    seen_urls = set()
    citations = []
    for title, url in re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', content):
        if url not in seen_urls:
            seen_urls.add(url)
            citations.append(Citation(title=title, url=url))

    return DeepResearchReport(
        query="Perfect RAG literature review",
        findings=content,
        citations=citations,
        research_successful=True,
        error_message=None,
    )


def _combine_research_findings(
    deep_research_report: Optional[DeepResearchReport],
    perfect_rag_report: Optional[DeepResearchReport] = None,
) -> Tuple[Optional[str], Optional[DeepResearchReport]]:
    """Combine deep research and perfect RAG findings into unified text and report.

    Returns:
        Tuple of (combined_text for SynthesisAgent, combined_report for CriticAgent).
        Returns (None, None) if no research is available.
    """
    texts = []
    all_citations = []
    seen_urls = set()

    if deep_research_report and deep_research_report.research_successful and deep_research_report.findings:
        texts.append("=== DEEP RESEARCH FINDINGS ===\n")
        texts.append(deep_research_report.findings)
        if deep_research_report.citations:
            texts.append("\n\nKey Citations:\n")
            for i, c in enumerate(deep_research_report.citations, 1):
                texts.append(f"  {i}. {c.title} ({c.url})\n")
        texts.append("\n=== END DEEP RESEARCH FINDINGS ===\n\n")
        for c in deep_research_report.citations:
            if c.url not in seen_urls:
                seen_urls.add(c.url)
                all_citations.append(c)

    if perfect_rag_report and perfect_rag_report.research_successful and perfect_rag_report.findings:
        texts.append("=== CURATED LITERATURE REVIEW ===\n")
        texts.append(perfect_rag_report.findings)
        texts.append("\n=== END CURATED LITERATURE REVIEW ===\n")
        for c in perfect_rag_report.citations:
            if c.url not in seen_urls:
                seen_urls.add(c.url)
                all_citations.append(c)

    if not texts:
        return None, None

    combined_text = "".join(texts)
    combined_report = DeepResearchReport(
        query="Combined deep research + perfect RAG findings",
        findings=combined_text,
        citations=all_citations,
        research_successful=True,
        error_message=None,
    )
    return combined_text, combined_report


async def run_network_workflow(
    target_molecule: str,
    confidence_threshold: float = 0.8,
    max_retries: int = 3,
    enable_deep_research: bool = False,
    enable_perfect_rag: bool = False,
    enable_io_logging: bool = True,
    num_pathways: int = 3,
    deep_research_cache_file: Optional[str] = None,
    perfect_rag_cache_file: Optional[str] = None,
    config_label: Optional[str] = None,
    run_number: Optional[int] = None,
    output_dir: str = "outputs",
) -> Tuple[NetworkSynthesisResult, str]:
    """
    Run the network synthesis workflow.

    Flow:
    1. Load research findings (deep research and/or perfect RAG, from cache or API)
    2. SynthesisNetworkAgent generates complete network (with research context)
    3. Critic evaluation (with research context)
    4. If confidence < threshold, retry with feedback

    Args:
        target_molecule: Target molecule to synthesize
        confidence_threshold: Minimum confidence to accept (default: 0.8)
        max_retries: Maximum retry attempts (default: 3)
        enable_deep_research: Enable deep research verification (default: False)
        enable_perfect_rag: Enable curated perfect RAG literature review (default: False)
        enable_io_logging: Enable I/O logging (default: True)
        num_pathways: Number of pathways to generate (default: 3)
        deep_research_cache_file: Path to cached deep research JSONL file (default: None)
        perfect_rag_cache_file: Path to cached perfect RAG markdown file (default: None)
        config_label: Label for this config run, used in output filenames (default: None)
        run_number: Run number for multi-run experiments (default: None)
        output_dir: Directory to write result JSON files into (default: "outputs")

    Returns:
        Tuple of (NetworkSynthesisResult, output_path)
    """
    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_suffix = f"_{config_label}" if config_label else ""
    if run_number is not None:
        log_suffix += f"_run{run_number}"
    log_file = Path(f"logs/network_workflow_{timestamp}{log_suffix}.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)

    logger.info(f"Starting network synthesis workflow for: {target_molecule}")
    logger.info(f"Config: {config_label or 'default'}")
    logger.info(f"Settings: threshold={confidence_threshold}, retries={max_retries}, "
                f"deep_research={enable_deep_research}, "
                f"perfect_rag={enable_perfect_rag}")

    # Setup I/O logger (include config_label in filename for separation)
    io_logger = None
    if enable_io_logging:
        log_target = target_molecule
        if config_label:
            log_target += f"_{config_label}"
        if run_number is not None:
            log_target += f"_run{run_number}"
        io_logger = IOLogger(target_molecule=log_target)
        logger.info(f"I/O logging enabled: {io_logger.log_file}")

    # Initialize agents
    network_agent = SynthesisNetworkAgent(io_logger=io_logger)
    critic_agent = CriticAgent(io_logger=io_logger)

    # --- Load research findings (deep research and/or perfect RAG) ---
    deep_research_report = None
    perfect_rag_report = None

    # Load deep research if enabled
    if enable_deep_research:
        if deep_research_cache_file:
            logger.info("=" * 60)
            logger.info(f"CACHED DEEP RESEARCH: Loading from {deep_research_cache_file}")
            logger.info("=" * 60)
            try:
                deep_research_report = _load_cached_deep_research(deep_research_cache_file)
                if deep_research_report.research_successful:
                    logger.info(
                        f"Cached deep research loaded: {len(deep_research_report.findings)} chars, "
                        f"{len(deep_research_report.citations)} citations"
                    )
                else:
                    logger.warning(f"Deep research cache indicates failure: {deep_research_report.error_message}")
                    deep_research_report = None
            except Exception as e:
                logger.error(f"Failed to load cached deep research: {str(e)}. Continuing without.")
                deep_research_report = None
        else:
            # Call API (existing behavior for non-cached runs)
            research_agent = AstroDeepResearchAgent(io_logger=io_logger)
            logger.info("=" * 60)
            logger.info("UPFRONT DEEP RESEARCH: Researching target molecule...")
            logger.info("=" * 60)
            try:
                deep_research_report = await research_agent.research_target_molecule(target_molecule)
                if deep_research_report.research_successful:
                    logger.info(
                        f"Deep research completed: {len(deep_research_report.findings)} chars, "
                        f"{len(deep_research_report.citations)} citations"
                    )
                else:
                    logger.warning(
                        f"Deep research failed: {deep_research_report.error_message}. "
                        f"Continuing without research findings."
                    )
                    deep_research_report = None
            except Exception as e:
                logger.error(f"Deep research error: {str(e)}. Continuing without research findings.")
                deep_research_report = None

    # Load perfect RAG if enabled
    if enable_perfect_rag and perfect_rag_cache_file:
        logger.info("=" * 60)
        logger.info(f"CACHED PERFECT RAG: Loading from {perfect_rag_cache_file}")
        logger.info("=" * 60)
        try:
            perfect_rag_report = _load_cached_perfect_rag(perfect_rag_cache_file)
            if perfect_rag_report.research_successful:
                logger.info(
                    f"Perfect RAG loaded: {len(perfect_rag_report.findings)} chars, "
                    f"{len(perfect_rag_report.citations)} citations"
                )
            else:
                logger.warning("Perfect RAG cache empty or failed")
                perfect_rag_report = None
        except Exception as e:
            logger.error(f"Failed to load perfect RAG cache: {str(e)}. Continuing without.")
            perfect_rag_report = None

    # Combine findings for agents
    deep_research_text, effective_report = _combine_research_findings(
        deep_research_report, perfect_rag_report
    )

    # Log loaded research content to IO log
    if io_logger:
        if deep_research_report and deep_research_report.research_successful:
            log_research_content(
                io_logger,
                agent_name="AstroDeepResearchAgent",
                content=deep_research_report.findings,
                source_file=deep_research_cache_file,
                config_label=config_label,
            )
        if perfect_rag_report and perfect_rag_report.research_successful:
            log_research_content(
                io_logger,
                agent_name="PerfectRAG",
                content=perfect_rag_report.findings,
                source_file=perfect_rag_cache_file,
                config_label=config_label,
            )

    if deep_research_text:
        logger.info(f"Research context prepared: {len(deep_research_text)} chars total")
    else:
        logger.info("No research context available for this run")

    # Track failed attempts
    failed_attempts = []
    best_network = None
    best_evaluation = None
    best_confidence = 0.0

    for attempt in range(1, max_retries + 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"ATTEMPT {attempt}/{max_retries}")
        logger.info(f"{'='*60}")

        # Step 1: Generate network (with LLM retry on transient failures)
        network = None
        for llm_retry in range(1, MAX_LLM_RETRIES + 1):
            try:
                logger.info(f"Step 1: Generating synthesis network (LLM call {llm_retry}/{MAX_LLM_RETRIES})...")
                network = await network_agent.generate_synthesis_network(
                    target_molecule=target_molecule,
                    num_pathways=num_pathways,
                    failed_attempts=failed_attempts if failed_attempts else None,
                    deep_research_findings=deep_research_text
                )
                logger.info(f"Generated network: {network.molecule_count} molecules, "
                           f"{network.reaction_count} reactions, {len(network.pathways)} pathways")
                break  # Success
            except Exception as e:
                logger.error(f"Network generation LLM error (retry {llm_retry}/{MAX_LLM_RETRIES}): {str(e)}")
                if llm_retry == MAX_LLM_RETRIES:
                    logger.error("Network generation failed after all LLM retries")
                    failed_attempts.append({
                        "attempt": attempt,
                        "confidence": 0.0,
                        "feedback": f"Network generation error: {str(e)}",
                        "issues": [str(e)]
                    })
                else:
                    logger.info("Waiting 120 seconds before retrying network generation...")
                    await asyncio.sleep(120)

        if network is None:
            continue  # Move to next attempt

        # Step 2: Research context info
        if effective_report:
            logger.info("Step 2: Using research findings for evaluation")

        # Step 3: Critic evaluation (with LLM retry on transient failures)
        evaluation = None
        for llm_retry in range(1, MAX_LLM_RETRIES + 1):
            try:
                logger.info(f"Step 3: Critic evaluation (LLM call {llm_retry}/{MAX_LLM_RETRIES})...")
                evaluation = await critic_agent.evaluate_network(
                    network=network,
                    deep_research_report=effective_report
                )
                logger.info(f"Evaluation: confidence={evaluation.overall_confidence:.3f}, "
                           f"approved={evaluation.approved}")
                break  # Success
            except Exception as e:
                logger.error(f"Critic evaluation LLM error (retry {llm_retry}/{MAX_LLM_RETRIES}): {str(e)}")
                if llm_retry == MAX_LLM_RETRIES:
                    logger.error("Critic evaluation failed after all LLM retries")
                    failed_attempts.append({
                        "attempt": attempt,
                        "confidence": 0.0,
                        "feedback": f"Critic evaluation error: {str(e)}",
                        "issues": [str(e)]
                    })
                else:
                    logger.info("Waiting 60 seconds before retrying critic evaluation...")
                    await asyncio.sleep(60)

        if evaluation is None:
            continue  # Move to next attempt

        # Track best result
        if evaluation.overall_confidence > best_confidence:
            best_network = network
            best_evaluation = evaluation
            best_confidence = evaluation.overall_confidence

        # Save this attempt's result
        attempt_result = NetworkSynthesisResult(
            target_molecule=target_molecule,
            network=network,
            evaluation=evaluation,
            success=evaluation.overall_confidence >= confidence_threshold,
            attempts=attempt
        )
        _save_result(attempt_result, target_molecule, timestamp, attempt=attempt, config_label=config_label, run_number=run_number, output_dir=output_dir)

        # Check if approved
        if evaluation.overall_confidence >= confidence_threshold:
            logger.info(f"Network APPROVED with confidence {evaluation.overall_confidence:.3f}")

            result = NetworkSynthesisResult(
                target_molecule=target_molecule,
                network=network,
                evaluation=evaluation,
                success=True,
                attempts=attempt
            )

            # Save output
            output_path = _save_result(result, target_molecule, timestamp, config_label=config_label, run_number=run_number, output_dir=output_dir)

            # Close I/O logger
            if io_logger:
                io_logger.close()

            return result, output_path

        # Record failure for retry
        logger.info(f"Network REJECTED (confidence {evaluation.overall_confidence:.3f} < {confidence_threshold})")
        failed_attempts.append({
            "attempt": attempt,
            "confidence": evaluation.overall_confidence,
            "feedback": evaluation.network_feedback,
            "issues": [pe.feedback for pe in evaluation.pathway_evaluations if not pe.approved]
        })

    # Max retries reached - return best result
    logger.warning(f"Max retries reached. Returning best result (confidence={best_confidence:.3f})")

    if best_network and best_evaluation:
        result = NetworkSynthesisResult(
            target_molecule=target_molecule,
            network=best_network,
            evaluation=best_evaluation,
            success=best_evaluation.approved,
            attempts=max_retries,
            notes=f"Max retries reached. Best confidence: {best_confidence:.3f}"
        )
    else:
        # No successful network generated
        empty_network = SynthesisNetwork(
            target_molecule=target_molecule,
            overall_strategy="Failed to generate network",
            molecules=[],
            reactions=[],
            pathways=[],
            hub_molecules=[],
            convergence_points=[]
        )
        empty_evaluation = NetworkEvaluation(
            target_molecule=target_molecule,
            pathway_evaluations=[],
            best_pathway_id="",
            overall_confidence=0.0,
            network_feedback="Failed to generate viable network",
            approved=False
        )
        result = NetworkSynthesisResult(
            target_molecule=target_molecule,
            network=empty_network,
            evaluation=empty_evaluation,
            success=False,
            attempts=max_retries,
            notes="Failed to generate viable network after all retries"
        )

    output_path = _save_result(result, target_molecule, timestamp, config_label=config_label, run_number=run_number, output_dir=output_dir)

    if io_logger:
        io_logger.close()

    return result, output_path


def _save_result(
    result: NetworkSynthesisResult,
    target_molecule: str,
    timestamp: str,
    attempt: int = None,
    config_label: str = None,
    run_number: int = None,
    output_dir: str = "outputs",
) -> str:
    """Save the synthesis result to a JSON file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = target_molecule.replace(" ", "_").replace("-", "_")
    parts = [f"network_{safe_name}_{timestamp}"]
    if config_label:
        parts.append(config_label)
    if run_number is not None:
        parts.append(f"run{run_number}")
    if attempt is not None:
        parts.append(f"attempt{attempt}")

    output_path = output_dir / f"{'_'.join(parts)}.json"

    with open(output_path, "w") as f:
        json.dump(result.model_dump(), f, indent=2, default=str)

    logger.info(f"Results saved to: {output_path}")
    return str(output_path)
