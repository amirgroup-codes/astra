#!/usr/bin/env python3
"""
Astra ablation pipeline — a single CLI for the three workflow stages.

Stages (run individually or end-to-end with `all`):

  1. generate  — SynthesisNetworkAgent + CriticAgent produce networks.
                 Writes outputs/{provider}/network_*.json
  2. inchi     — backfill InChI from PubChem (replaces inchi_corrected.sh).
                 outputs/{provider}/ -> outputs_inchi_corrected/{provider}/
  3. validate  — score networks against ChemOrigins reference data.
                 outputs_inchi_corrected/{provider}/ -> validation_report/{provider}/

Examples:
    python pipeline.py generate --molecules L-Alanine --runs 1 --provider claude
    python pipeline.py inchi --provider claude
    python pipeline.py validate --provider claude
    python pipeline.py all --molecules L-Alanine,Glycine --provider claude

The model backend is the MODEL_PROVIDER env var (config.env); --provider overrides it
and also names the per-provider output subfolder so the three stages chain automatically.
"""
import argparse
import asyncio
import csv
import glob
import json
import math
import os
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Generation ablation configs, keyed by label. Each toggles one research-context
# source. `deep_research_dir` points at the cached deep-research text directory.
ABLATION_CONFIGS: Dict[str, Dict[str, Any]] = {
    # "deep_research_claude": {
    #     "description": "Deep Research from Claude",
    #     "enable_deep_research": True,
    #     "enable_perfect_rag": False,
    #     "deep_research_dir": "reports/deep_research_claude",

    # },
    # "deep_research_gemini": {
    #     "description": "Deep Research from Gemini",
    #     "enable_deep_research": True,
    #     "enable_perfect_rag": False,
    #     "deep_research_dir": "reports/deep_research_gemini",
    # },
    "deep_research_gpt5.4": {
        "description": "Deep Research from ChatGPT",
        "enable_deep_research": True,
        "enable_perfect_rag": False,
        "deep_research_dir": "reports/deep_research_gpt5.4",
    },


    # "perfect_rag": {
    #     "description": "Perfect RAG only",
    #     "enable_deep_research": False,
    #     "enable_perfect_rag": True,
    # },
    # "no_research": {
    #     "description": "Baseline: No research",
    #     "enable_deep_research": False,
    #     "enable_perfect_rag": False,
    # },
}

# Configs the validator scans for in filenames. Includes "Naive" (the no-agent
# baseline produced under naive_approach/), which generation does not emit.
VALIDATION_CONFIGS = [
    "no_research", "deep_research_claude", "deep_research_gemini",
    "deep_research_gpt5.4", "perfect_rag", "Naive"
]
CONFIG_DESCRIPTIONS = {
    "no_research": "Baseline: No research",
    "deep_research_claude": "Deep Research from Claude",
    "deep_research_gemini": "Deep Research from Gemini",
    "deep_research_gpt5.4": "Deep Research from ChatGPT",
    "perfect_rag": "Perfect RAG",
    "Naive": "Naive",
}

DEFAULT_MOLECULES = ["L-Alanine","Glycine","Serine","Arginine","Threonine","Valine"]
DEFAULT_GENERATE_CONFIGS = ["deep_research_gpt5.4"]


# Known molecule names (handy reference for --molecules; not all have cached research).
KNOWN_MOLECULES = [
    "L-Alanine", "Serine", "Arginine", "Threonine", "Valine", "L-Proline",
    "Glycine", "Glutamate", "Histidine", "ATP", "Acetyl-CoA", "Adenine",
    "Asparagine", "Aspartic-Acid", "Cysteine", "Cytosine", "Decanoic-Acid",
    "Glucose", "Glutamine", "Guanine", "Isoleucine", "Leucine", "Lysine",
    "Methionine", "Nicotinamide", "Oxaloacetate", "Phenylalanine", "Pyruvate",
    "Ribose", "Thymine", "Tryptophan", "Tyrosine", "Uracil",
]

# Cache directories for run-specific research context.
PERFECT_RAG_DIR = "reports/perfect_rag"

# Pacing between LLM runs to avoid rate limiting (seconds).
PAUSE_BETWEEN_RUNS = 120
PAUSE_BETWEEN_CONFIGS = 30
PAUSE_BETWEEN_MOLECULES = 180


def _split_csv(value: Optional[str]) -> List[str]:
    """Split a comma-separated CLI value into a clean list."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def resolve_provider(args, required: bool) -> Optional[str]:
    """Resolve the model provider / output subfolder name.

    --provider overrides MODEL_PROVIDER (and is exported so client factories see it).
    Returns None when not required and unset (callers then iterate all subfolders).
    """
    provider = getattr(args, "provider", None) or os.getenv("MODEL_PROVIDER", "")
    provider = provider.strip()
    if provider:
        os.environ["MODEL_PROVIDER"] = provider
        return provider
    if required:
        print("ERROR: no provider given. Pass --provider <name> or set MODEL_PROVIDER "
              "in config.env (claude, gpt41, gpt5.4_openai, gpt5.4_agent_azure).")
    return None


# ===========================================================================
# Stage 1: generate
# ===========================================================================

def print_provider_info(provider: str) -> None:
    """Display the active model backend."""
    p = provider.lower()
    if p == "claude":
        model_name = os.getenv("CLAUDE_MODEL", "claude-opus-4-5-20251101")
        print(f"  Model Provider: Anthropic Claude")
        print(f"  Model: {model_name}")
        if os.getenv("CLAUDE_ENABLE_THINKING", "true").lower() == "true":
            budget = os.getenv("CLAUDE_THINKING_BUDGET", "10000")
            print(f"  Extended Thinking: Enabled (budget: {budget} tokens)")
    elif p == "gpt41":
        print(f"  Model Provider: Azure OpenAI (GPT-4.1)")
        print(f"  Model: {os.getenv('AZURE_GPT41_DEPLOYMENT_NAME', 'gpt-4.1')}")
    elif p == "gpt5.4_openai":
        print(f"  Model Provider: OpenAI Direct (GPT-5.4)")
        print(f"  Model: {os.getenv('OPENAI_DIRECT_MODEL', 'gpt-5.4')}")
    elif p == "gpt5.4_agent_azure":
        print(f"  Model Provider: Azure AI Projects Agent (GPT-5.4)")
        print(f"  Model: {os.getenv('AZURE_AGENT_NAME', 'gpt-5.4')}")
    else:
        print(f"  Model Provider: UNKNOWN/UNSUPPORTED ({provider!r})")
        print(f"  Set --provider/MODEL_PROVIDER to: claude, gpt41, gpt5.4_openai, gpt5.4_agent_azure")


def resolve_cache_files(molecule: str, run_number: int = 1, deep_research_dir: str = None):
    """Resolve cache file paths for a molecule and run number.

    Deep research uses run-specific files: {molecule}-Run{N}.txt
    Perfect RAG uses the same file for all runs: {molecule}.md
    """
    from core.network_workflow import _find_file_case_insensitive
    dr_path = None
    if deep_research_dir:
        dr_path = _find_file_case_insensitive(deep_research_dir, f"{molecule}-Run{run_number}.txt")
    rag_path = _find_file_case_insensitive(PERFECT_RAG_DIR, f"{molecule}.md")
    return dr_path, rag_path


def find_completed_runs(output_dir: str = "outputs"):
    """Scan output directory for already-completed (molecule, config, run) combinations.

    Looks for final result files (without '_attempt') matching
    network_{safe_name}_{timestamp}_{config}_run{N}.json.

    Returns a set of (safe_name, config_label, run_number) tuples.
    """
    completed = set()
    output_path = Path(output_dir)
    if not output_path.exists():
        return completed

    pattern = re.compile(r'^network_(.+?)_\d{8}_\d{6}_(.+?)_run(\d+)\.json$')
    for f in output_path.iterdir():
        if '_attempt' in f.name:
            continue
        m = pattern.match(f.name)
        if m:
            completed.add((m.group(1), m.group(2), int(m.group(3))))
    return completed


def print_network_results(result, output_path: str) -> None:
    """Print a summary of the network synthesis results."""
    print("\n" + "=" * 70)
    print("NETWORK SYNTHESIS WORKFLOW RESULTS")
    print("=" * 70)
    print(f"\nTarget Molecule: {result.target_molecule}")
    print(f"Overall Success: {'Yes' if result.success else 'No'}")
    print(f"Attempts: {result.attempts}")

    if result.notes:
        print(f"\nNotes: {result.notes}")

    network = result.network
    print("\n" + "-" * 70)
    print("NETWORK SUMMARY:")
    print("-" * 70)
    print(f"\nStrategy: {network.overall_strategy}")
    print(f"Molecules: {len(network.molecules)} nodes")
    print(f"Reactions: {len(network.reactions)} nodes")
    print(f"Pathways: {len(network.pathways)}")
    print(f"Hub Molecules: {', '.join(network.hub_molecules) if network.hub_molecules else 'None'}")

    print("\n" + "-" * 70)
    print("MOLECULES:")
    print("-" * 70)
    for mol in network.molecules:
        print(f"  - {mol.id}: {mol.formula} ({mol.common_name or mol.iupac_name}) [{mol.role}]")

    print("\n" + "-" * 70)
    print("REACTIONS:")
    print("-" * 70)
    for rxn in network.reactions:
        print(f"  - {rxn.id}: {', '.join(rxn.inputs)} -> {', '.join(rxn.outputs)}")
        print(f"    Name: {rxn.name}")
        print(f"    Environment: {rxn.environment}")
        print(f"    Mechanism: {rxn.mechanism[:100]}..." if len(rxn.mechanism) > 100
              else f"    Mechanism: {rxn.mechanism}")

    print("\n" + "-" * 70)
    print("PATHWAYS:")
    print("-" * 70)
    for pathway in network.pathways:
        print(f"\n  {pathway.pathway_id}: {pathway.name}")
        print(f"    Description: {pathway.description}")
        print(f"    Reactions: {' -> '.join(pathway.reaction_sequence)}")
        print(f"    Key intermediates: {', '.join(pathway.key_intermediates)}")

    print("\n" + "-" * 70)
    print("EVALUATION:")
    print("-" * 70)
    eval_result = result.evaluation
    print(f"\nOverall Confidence: {eval_result.overall_confidence:.3f}")
    print(f"Approved: {eval_result.approved}")
    print(f"Best Pathway: {eval_result.best_pathway_id}")
    print(f"Hub Quality: {eval_result.hub_quality:.3f}")
    print(f"Convergence Quality: {eval_result.convergence_quality:.3f}")
    print(f"\nFeedback: {eval_result.network_feedback}")

    print("\n" + "=" * 70)
    print(f"\nDetailed results saved to: {output_path}")
    print("=" * 70 + "\n")


def print_ablation_summary(results) -> None:
    """Print a formatted summary table of ablation results."""
    print("\n" + "=" * 90)
    print("ABLATION STUDY SUMMARY")
    print("=" * 90)
    print(f"{'Molecule':<20} {'Config':<12} {'Run':<6} {'Description':<30} {'Status':<10} "
          f"{'Confidence':<12} {'Approved':<10} {'Attempts':<8}")
    print("-" * 100)
    for r in results:
        conf = f"{r['confidence']:.3f}" if "confidence" in r else "N/A"
        print(f"{r['molecule'][:18]:<20} {r['config']:<12} {str(r.get('run', 'N/A')):<6} "
              f"{r.get('description', '')[:28]:<30} {r['status']:<10} {conf:<12} "
              f"{str(r.get('approved', 'N/A')):<10} {str(r.get('attempts', 'N/A')):<8}")
    print("=" * 100)


def _save_ablation_summary(results, output_dir: str) -> None:
    """Save ablation summary to a JSON file inside the provider output directory."""
    summary_path = Path(output_dir) / f"ablation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nAblation summary saved to: {summary_path}")


async def cmd_generate(args) -> int:
    """Run the generation ablation study over molecules x configs x runs."""
    provider = resolve_provider(args, required=True)
    if not provider:
        return 1

    from core.network_workflow import run_network_workflow  # noqa: F401 (env set first)

    molecules = _split_csv(args.molecules) or list(DEFAULT_MOLECULES)
    config_labels = _split_csv(args.configs) or list(DEFAULT_GENERATE_CONFIGS)
    unknown = [c for c in config_labels if c not in ABLATION_CONFIGS]
    if unknown:
        print(f"ERROR: unknown config(s): {', '.join(unknown)}")
        print(f"  Available: {', '.join(ABLATION_CONFIGS)}")
        return 1
    configs = [dict(label=c, **ABLATION_CONFIGS[c]) for c in config_labels]

    num_runs = args.runs
    output_dir = f"outputs/{provider}"

    print("\n" + "=" * 70)
    print("AutoGen Molecular Synthesis - Ablation Study (generate)")
    print("=" * 70)
    print_provider_info(provider)

    print(f"\n  Ablation Configs: {len(configs)}")
    for cfg in configs:
        print(f"    {cfg['label']}: {cfg['description']}")
    print(f"  Target Molecules: {len(molecules)}")
    print(f"  Runs per Config: {num_runs}")
    print(f"  Total Runs: {len(molecules) * len(configs) * num_runs}")
    print(f"  Confidence Threshold: {args.confidence_threshold}")
    print(f"  Max Retries: {args.max_retries}")
    print(f"  Number of Pathways: {args.num_pathways}")
    print(f"  I/O Logging: {'Enabled' if args.io_logging else 'Disabled'}")
    print(f"  Output Dir: {output_dir}")

    completed = find_completed_runs(output_dir)
    if completed:
        print(f"\n  Resume: {len(completed)} completed runs found (will be skipped)")
    else:
        print(f"\n  Resume: No previous runs found")

    results_summary: List[Dict[str, Any]] = []

    for mol_idx, target_molecule in enumerate(molecules):
        print(f"\n{'#' * 70}")
        print(f"# MOLECULE {mol_idx + 1}/{len(molecules)}: {target_molecule}")
        print(f"{'#' * 70}")

        for cfg_idx, config in enumerate(configs):
            label = config["label"]
            description = config["description"]
            print(f"\n  {'~' * 60}")
            print(f"  {label}: {description}")
            print(f"  {'~' * 60}")

            for run_num in range(1, num_runs + 1):
                print(f"\n    --- Run {run_num}/{num_runs} ---")

                safe_name = target_molecule.replace(" ", "_").replace("-", "_")
                if (safe_name, label, run_num) in completed:
                    print(f"    SKIP: Already completed (found in {output_dir}/)")
                    continue

                dr_cache, rag_cache = resolve_cache_files(
                    target_molecule, run_num, deep_research_dir=config.get("deep_research_dir"),
                )
                print(f"    Deep Research cache: {dr_cache or 'NOT FOUND'}")
                print(f"    Perfect RAG cache:   {rag_cache or 'NOT FOUND'}")

                dr_file = dr_cache if config["enable_deep_research"] else None
                rag_file = rag_cache if config.get("enable_perfect_rag") else None

                # Skip if a required research cache is missing.
                missing = None
                if config["enable_deep_research"] and not dr_cache:
                    missing = "no DR cache"
                elif config.get("enable_perfect_rag") and not rag_cache:
                    missing = "no perfect RAG cache"
                if missing:
                    print(f"    SKIP: {missing} for {target_molecule} Run{run_num}")
                    results_summary.append({
                        "molecule": target_molecule, "config": label, "run": run_num,
                        "description": description, "status": "skipped", "reason": missing,
                    })
                    continue

                try:
                    result, output_path = await run_network_workflow(
                        target_molecule=target_molecule,
                        confidence_threshold=args.confidence_threshold,
                        max_retries=args.max_retries,
                        enable_deep_research=config["enable_deep_research"],
                        enable_perfect_rag=config.get("enable_perfect_rag", False),
                        enable_io_logging=args.io_logging,
                        num_pathways=args.num_pathways,
                        deep_research_cache_file=dr_file,
                        perfect_rag_cache_file=rag_file,
                        config_label=label,
                        run_number=run_num,
                        output_dir=output_dir,
                    )

                    confidence = result.evaluation.overall_confidence
                    approved = result.evaluation.approved
                    print(f"    Result: confidence={confidence:.3f}, approved={approved}, attempts={result.attempts}")
                    print(f"    Output: {output_path}")
                    print_network_results(result, output_path)

                    results_summary.append({
                        "molecule": target_molecule, "config": label, "run": run_num,
                        "description": description, "status": "completed",
                        "confidence": confidence, "approved": approved,
                        "attempts": result.attempts, "output_path": output_path,
                    })

                except KeyboardInterrupt:
                    print("\n\nWorkflow interrupted by user.")
                    _save_ablation_summary(results_summary, output_dir)
                    return 1

                except Exception as e:
                    print(f"    ERROR: {type(e).__name__}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    results_summary.append({
                        "molecule": target_molecule, "config": label, "run": run_num,
                        "description": description, "status": "error", "error": str(e),
                    })

                if run_num < num_runs:
                    print(f"\n    Pausing {PAUSE_BETWEEN_RUNS // 60} minutes before next run...")
                    await asyncio.sleep(PAUSE_BETWEEN_RUNS)

            # Pause between configs (skip after the last config).
            if cfg_idx < len(configs) - 1:
                await asyncio.sleep(PAUSE_BETWEEN_CONFIGS)

        # Pause between molecules (skip after the last molecule).
        if mol_idx < len(molecules) - 1:
            print(f"\nPausing {PAUSE_BETWEEN_MOLECULES // 60} minutes before next molecule...")
            await asyncio.sleep(PAUSE_BETWEEN_MOLECULES)

    print_ablation_summary(results_summary)
    _save_ablation_summary(results_summary, output_dir)
    return 0


# ===========================================================================
# Stage 2: inchi (replaces inchi_corrected.sh)
# ===========================================================================

def cmd_inchi(args) -> int:
    """Backfill InChI from PubChem for every generated network.

    outputs/{provider}/network_*.json -> outputs_inchi_corrected/{provider}/
    Skips files already corrected. With no --provider, processes every subfolder.
    """
    from pubchem_inchi_lookup import process_network_file

    in_base = Path("outputs")
    out_base = Path("outputs_inchi_corrected")

    if not in_base.exists():
        print(f"ERROR: {in_base}/ does not exist — run `generate` first.")
        return 1

    provider = getattr(args, "provider", None)
    if provider:
        providers = [provider]
    else:
        providers = sorted(d.name for d in in_base.iterdir() if d.is_dir())
    if not providers:
        print(f"ERROR: no provider subfolders under {in_base}/.")
        return 1

    print("\n" + "=" * 70)
    print("InChI correction (PubChem lookup)")
    print(f"  Providers: {', '.join(providers)}")
    print("=" * 70)

    total = 0
    for prov in providers:
        src_dir = in_base / prov
        if not src_dir.is_dir():
            print(f"\n  WARN: {src_dir}/ not found, skipping")
            continue
        dst_dir = out_base / prov
        dst_dir.mkdir(parents=True, exist_ok=True)

        for src in sorted(src_dir.glob("network_*.json")):
            dst = dst_dir / src.name
            if dst.exists():
                print(f"=== Skipping (already exists): {prov}/{src.name} ===")
                continue
            print(f"=== Processing: {prov}/{src.name} ===")
            process_network_file(str(src), str(dst))
            total += 1
            print("")

    print(f"\nInChI correction complete. {total} file(s) processed.")
    return 0


# ===========================================================================
# Stage 3: validate
# ===========================================================================

@dataclass
class TableRow:
    model: str
    molecule: str
    config: str
    iteration: str       # "1", "2", ... or "Final"
    confidence: Optional[float]
    recall_score: float
    precision_score: Optional[float]
    molecule_match: Optional[float] = None
    recall_75pct: Optional[float] = None
    recall_100pct: Optional[float] = None
    count_75: Optional[int] = None
    count_100: Optional[int] = None
    count_total: Optional[int] = None


def extract_output_molecules(network_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract molecules from network output JSON."""
    return network_data.get("network", {}).get("molecules", [])


def extract_reference_molecules(reference_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract unique molecules (reactants + products) from reference JSON."""
    molecules = {}
    for reaction in reference_data.get("reactions", []):
        for mol in reaction.get("reactants", []) + reaction.get("products", []):
            key = mol.get("key")
            if key and key not in molecules:
                molecules[key] = mol
    return list(molecules.values())


def normalize_name(name: Optional[str]) -> str:
    """Normalize a name for comparison (lowercase, strip whitespace)."""
    return name.lower().strip() if name else ""


def find_best_match(
    output_mol: Dict[str, Any],
    ref_molecules: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], float, str]:
    """Find the best matching reference molecule (exact name or exact InChI only)."""
    from agents.validators.rdkit_similarity import compute_molecule_similarity

    output_common = normalize_name(output_mol.get("common_name"))
    if output_common:
        for ref_mol in ref_molecules:
            if output_common == normalize_name(ref_mol.get("title")):
                return (ref_mol, 1.0, "common_name")

    output_iupac = normalize_name(output_mol.get("iupac_name"))
    if output_iupac:
        for ref_mol in ref_molecules:
            if output_iupac == normalize_name(ref_mol.get("title")):
                return (ref_mol, 1.0, "iupac_name")

    output_inchi = output_mol.get("inchi", "")
    if output_inchi:
        for ref_mol in ref_molecules:
            ref_inchi = ref_mol.get("inchi", "")
            if ref_inchi and compute_molecule_similarity(output_inchi, ref_inchi) == 1.0:
                return (ref_mol, 1.0, "inchi")

    return (None, 0.0, "none")


def compute_molecule_statistics(network_file: str, reference_file: str) -> Dict[str, Any]:
    """Compute exact-match molecule statistics between output and reference files."""
    with open(network_file, 'r') as f:
        network_data = json.load(f)
    with open(reference_file, 'r') as f:
        reference_data = json.load(f)

    output_molecules = extract_output_molecules(network_data)
    ref_molecules = extract_reference_molecules(reference_data)

    matches = []
    common_name_matches = iupac_name_matches = inchi_matches = 0

    for output_mol in output_molecules:
        best_match, score, match_type = find_best_match(output_mol, ref_molecules)
        if match_type == "none":
            continue
        matches.append({
            "output_molecule": {
                "common_name": output_mol.get("common_name"),
                "iupac_name": output_mol.get("iupac_name"),
                "formula": output_mol.get("formula"),
                "inchi": output_mol.get("inchi"),
            },
            "match_type": match_type,
            "reference_molecule": {
                "title": best_match.get("title"),
                "formula": best_match.get("formula"),
                "inchi": best_match.get("inchi"),
                "key": best_match.get("key"),
            },
        })
        if match_type == "common_name":
            common_name_matches += 1
        elif match_type == "iupac_name":
            iupac_name_matches += 1
        elif match_type == "inchi":
            inchi_matches += 1

    total_matched = common_name_matches + iupac_name_matches + inchi_matches
    total_output = len(output_molecules)
    coverage = (total_matched / total_output * 100) if total_output > 0 else 0.0

    return {
        "total_output_molecules": total_output,
        "total_reference_molecules": len(ref_molecules),
        "common_name_matches": common_name_matches,
        "iupac_name_matches": iupac_name_matches,
        "inchi_matches": inchi_matches,
        "total_matched": total_matched,
        "unmatched": total_output - total_matched,
        "coverage_percent": round(coverage, 1),
        "matches": matches,
    }


def print_molecule_statistics(stats: Dict[str, Any]) -> None:
    """Print molecule match statistics in a formatted way."""
    print("\n" + "-" * 60)
    print("MOLECULE MATCH STATISTICS (exact matches only)")
    print("-" * 60)
    print(f"  Output molecules:            {stats['total_output_molecules']}")
    print(f"  Reference molecules:         {stats['total_reference_molecules']}")
    print(f"  Matched by common_name:      {stats['common_name_matches']}")
    print(f"  Matched by iupac_name:       {stats['iupac_name_matches']}")
    print(f"  Matched by exact InChI:      {stats['inchi_matches']}")
    print(f"  Total matched:               {stats['total_matched']}")
    print(f"  Unmatched:                   {stats['unmatched']}")
    print(f"  Coverage:                    {stats['coverage_percent']}%")
    print("-" * 60)
    print("\nMatch Details:")
    for match in stats['matches']:
        output = match['output_molecule']
        output_name = output.get('common_name') or output.get('iupac_name') or output.get('formula') or 'Unknown'
        print(f"  [{match['match_type'].upper()}]  {output_name} <-> {match['reference_molecule'].get('title', 'N/A')}")


def compute_chemorigin_recall(network_file: str, reference_file: str) -> Dict[str, Any]:
    """Compute how much of the ChemOrigins reference is covered by the network."""
    from agents.validators.rdkit_similarity import compute_reaction_similarity
    from core.chemorigins_loader import ChemOriginsLoader

    with open(network_file, 'r') as f:
        network_data = json.load(f)

    loader = ChemOriginsLoader(reference_file)
    loader.load()

    if not loader.module:
        return {
            "network_file": network_file,
            "reference_file": reference_file,
            "total_reference_reactions": 0,
            "total_network_reactions": 0,
            "average_recall_score": 0.0,
            "reaction_recall": [],
        }

    network = network_data.get("network", {})
    molecules = {m["id"]: m for m in network.get("molecules", [])}

    network_reactions = []
    for rxn in network.get("reactions", []):
        network_reactions.append({
            "reaction_id": rxn.get("id"),
            "reaction_name": rxn.get("name"),
            "environment": rxn.get("environment"),
            "reactants": [molecules[mid] for mid in rxn.get("inputs", []) if mid in molecules],
            "products": [molecules[mid] for mid in rxn.get("outputs", []) if mid in molecules],
        })

    ref_reactions = loader.module.reactions
    reaction_recall = []

    for ref_rxn in ref_reactions:
        best_score = 0.0
        best_network_rxn_id = None
        best_network_rxn_name = None
        for net_rxn in network_reactions:
            score, _ = compute_reaction_similarity(net_rxn, ref_rxn)
            if score > best_score:
                best_score = score
                best_network_rxn_id = net_rxn.get("reaction_id")
                best_network_rxn_name = net_rxn.get("reaction_name")

        ref_reactant_strs = [f"{r.formula} ({r.title})" for r in ref_rxn.reactants]
        ref_product_strs = [f"{p.formula} ({p.title})" for p in ref_rxn.products]
        ref_reaction_str = f"{' + '.join(ref_reactant_strs)} -> {' + '.join(ref_product_strs)}"

        reaction_recall.append({
            "reference_reaction_key": ref_rxn.key,
            "reference_reaction": ref_reaction_str,
            "best_network_match": {
                "reaction_id": best_network_rxn_id,
                "reaction_name": best_network_rxn_name,
            },
            "recall_score": round(best_score, 4),
        })

    recall_scores = [rc["recall_score"] for rc in reaction_recall]
    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0

    return {
        "network_file": network_file,
        "reference_file": reference_file,
        "total_reference_reactions": len(ref_reactions),
        "total_network_reactions": len(network_reactions),
        "average_recall_score": round(avg_recall, 4),
        "reaction_recall": reaction_recall,
    }


def compute_recall_thresholds(reaction_recall: List[Dict[str, Any]]) -> Tuple[float, float, int, int, int]:
    """Compute fraction and count of reference reactions at >=75% and ==100% match."""
    if not reaction_recall:
        return 0.0, 0.0, 0, 0, 0
    n = len(reaction_recall)
    n_75 = sum(1 for r in reaction_recall if r["recall_score"] >= 0.75)
    n_100 = sum(1 for r in reaction_recall if r["recall_score"] == 1.0)
    return round(n_75 / n, 4), round(n_100 / n, 4), n_75, n_100, n


def print_chemorigin_recall(recall: Dict[str, Any]) -> None:
    """Print chemorigin recall statistics in a formatted way."""
    print("\n" + "-" * 60)
    print("CHEMORIGIN RECALL (reference -> network)")
    print("-" * 60)
    print(f"  Reference reactions:         {recall['total_reference_reactions']}")
    print(f"  Network reactions:           {recall['total_network_reactions']}")
    print(f"  Average recall score:        {recall['average_recall_score']:.4f}")
    print("-" * 60)
    print("\nPer-Reference-Reaction Recall:")
    for rc in recall["reaction_recall"]:
        score = rc["recall_score"]
        net_id = rc["best_network_match"]["reaction_id"] or "none"
        net_name = rc["best_network_match"]["reaction_name"] or ""
        if score >= 0.8:
            tag = "HIGH"
        elif score >= 0.5:
            tag = "MED "
        elif score > 0:
            tag = "LOW "
        else:
            tag = "NONE"
        print(f"  [{tag}] {rc['reference_reaction_key']} -> {net_id} (score: {score:.4f})")
        if net_name:
            print(f"         {net_name[:80]}")


def discover_files(molecule: str, config: str, model_dir: str) -> Tuple[List[str], Optional[str], Optional[str]]:
    """Discover attempt files, final file, and reference file for a molecule+config."""
    safe_molecule = molecule.replace(" ", "_").replace("-", "_")
    attempt_candidates = list(set(
        glob.glob(f"{model_dir}/network_{safe_molecule}_*_{config}_run*_attempt*.json")
        + glob.glob(f"{model_dir}/network_{safe_molecule}_{config}_run*_attempt*.json")
    ))
    attempt_files = sorted(
        attempt_candidates,
        key=lambda f: int(re.search(r'_attempt(\d+)', f).group(1)) if re.search(r'_attempt(\d+)', f) else 0,
    )

    all_outputs = list(set(
        glob.glob(f"{model_dir}/network_{safe_molecule}_*_{config}_run*.json")
        + glob.glob(f"{model_dir}/network_{safe_molecule}_{config}_run*.json")
    ))
    final_candidates = [f for f in all_outputs if "_attempt" not in f]
    final_file = final_candidates[0] if final_candidates else None

    ref_candidates = glob.glob(f"validator/pbmdl-*-{molecule}.json")
    reference_file = ref_candidates[0] if ref_candidates else None

    return attempt_files, final_file, reference_file


def extract_overall_confidence(json_path: str) -> Optional[float]:
    """Extract overall_confidence from a network output JSON file."""
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        return data.get("evaluation", {}).get("overall_confidence")
    except Exception:
        return None


def score_attempts(
    molecule: str,
    attempt_files: List[str],
    final_file: Optional[str],
    reference_file: str,
) -> List[Tuple[str, float, Optional[float], float, float, int, int, int]]:
    """Compute ChemOrigins recall + confidence for each attempt."""
    scores = []
    for attempt_path in attempt_files:
        match = re.search(r'_attempt(\d+)', attempt_path)
        label = f"Attempt {match.group(1)}" if match else Path(attempt_path).stem
        confidence = extract_overall_confidence(attempt_path)
        try:
            recall = compute_chemorigin_recall(attempt_path, reference_file)
            frac_75, frac_100, c75, c100, ctotal = compute_recall_thresholds(recall["reaction_recall"])
            scores.append((label, recall["average_recall_score"], confidence, frac_75, frac_100, c75, c100, ctotal))
        except Exception as e:
            print(f"  Warning: could not score {attempt_path}: {e}")
            scores.append((label, 0.0, confidence, 0.0, 0.0, 0, 0, 0))
    return scores


def plot_attempt_scores(all_scores, output_path: str) -> str:
    """Generate a PNG of recall/precision/confidence/mol-match across attempts per molecule."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    molecules = list(all_scores.keys())
    n = len(molecules)
    cols = min(n, 3)
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(8 * cols, 5 * rows), squeeze=False)
    config_legend = "  |  ".join(f"{k}: {v}" for k, v in CONFIG_DESCRIPTIONS.items())
    fig.suptitle(
        "Recall, Precision, Confidence & Mol Match Across Attempts\n" + config_legend,
        fontsize=12, y=1.03,
    )

    bar_width = 0.18
    config_gap = 1.5

    for idx, molecule in enumerate(molecules):
        r, c = divmod(idx, cols)
        ax = axes[r][c]

        x_positions, x_labels = [], []
        recall_vals, confidence_vals, precision_vals, mol_match_vals = [], [], [], []
        pos = 0.0
        for config_label in sorted(all_scores[molecule].keys()):
            for label, rec, conf, prec, mol_match in all_scores[molecule][config_label]:
                x_positions.append(pos)
                x_labels.append(f"{config_label}\n{label}")
                recall_vals.append(rec)
                confidence_vals.append(conf if conf is not None else 0.0)
                precision_vals.append(prec if prec is not None else 0.0)
                mol_match_vals.append(mol_match / 100.0 if mol_match is not None else 0.0)
                pos += 1.0
            pos += config_gap

        x_pos0 = [p - 1.5 * bar_width for p in x_positions]
        x_pos1 = [p - 0.5 * bar_width for p in x_positions]
        x_pos2 = [p + 0.5 * bar_width for p in x_positions]
        x_pos3 = [p + 1.5 * bar_width for p in x_positions]

        bars1 = ax.bar(x_pos0, recall_vals, bar_width, label="Recall", color="#4C72B0", edgecolor="white")
        bars2 = ax.bar(x_pos1, precision_vals, bar_width, label="Precision", color="#55A868", edgecolor="white")
        bars3 = ax.bar(x_pos2, confidence_vals, bar_width, label="Confidence", color="#DD8452", edgecolor="white")
        bars4 = ax.bar(x_pos3, mol_match_vals, bar_width, label="Mol Match", color="#8172B2", edgecolor="white")

        ax.set_ylim(0, 1.15)
        ax.set_ylabel("Score")
        ax.set_title(molecule.replace("_", " "), fontsize=11, fontweight="bold")
        ax.set_xticks(x_positions)
        ax.set_xticklabels(x_labels, fontsize=7, rotation=45, ha="right")
        ax.legend(fontsize=7, loc="upper right")

        for bars, vals in [(bars1, recall_vals), (bars2, precision_vals),
                           (bars3, confidence_vals), (bars4, mol_match_vals)]:
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                        f"{val:.2f}", ha="center", va="bottom", fontsize=5)

    for idx in range(n, rows * cols):
        r, c = divmod(idx, cols)
        axes[r][c].set_visible(False)

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nAttempt scores chart saved to: {output_path}")
    return output_path


def _mean_std_str(values: List[float], fmt: str = ".4f") -> str:
    """Format a list of values as '$mean \\pm std$' in LaTeX math mode."""
    if not values:
        return "--"
    avg = statistics.mean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    return f"${avg:{fmt}} \\pm {std:{fmt}}$"


def generate_latex_table(rows: List[TableRow], output_path: str) -> str:
    """Generate a LaTeX table of avg ± std recall/precision/mol-match per molecule+config."""
    from collections import defaultdict

    attempt_groups: Dict[Tuple[str, str], List[TableRow]] = defaultdict(list)
    final_map: Dict[Tuple[str, str], TableRow] = {}
    for row in rows:
        key = (row.molecule, row.config)
        if row.iteration == "Final":
            final_map[key] = row
        else:
            attempt_groups[key].append(row)

    @dataclass
    class SummaryRow:
        molecule: str
        config: str
        confidence: Optional[float]
        recall_mean: float
        recall_str: str
        precision_str: str
        mol_match_str: str
        recall_75pct_str: str
        recall_100pct_str: str
        count_75_str: str
        count_100_str: str
        count_total_str: str

    summary_rows: List[SummaryRow] = []
    for key, attempts in sorted(attempt_groups.items()):
        molecule, config = key
        recalls = [a.recall_score for a in attempts]
        precisions = [a.precision_score for a in attempts if a.precision_score is not None]
        mol_matches = [a.molecule_match for a in attempts if a.molecule_match is not None]
        r75s = [a.recall_75pct for a in attempts if a.recall_75pct is not None]
        r100s = [a.recall_100pct for a in attempts if a.recall_100pct is not None]
        c75s = [float(a.count_75) for a in attempts if a.count_75 is not None]
        c100s = [float(a.count_100) for a in attempts if a.count_100 is not None]
        ctotals = [float(a.count_total) for a in attempts if a.count_total is not None]

        final = final_map.get(key)
        confidence = final.confidence if final else attempts[-1].confidence

        summary_rows.append(SummaryRow(
            molecule=molecule,
            config=config,
            confidence=confidence,
            recall_mean=statistics.mean(recalls) if recalls else 0.0,
            recall_str=_mean_std_str(recalls, ".4f"),
            precision_str=_mean_std_str(precisions, ".2f"),
            mol_match_str=_mean_std_str(mol_matches, ".1f"),
            recall_75pct_str=_mean_std_str(r75s, ".4f"),
            recall_100pct_str=_mean_std_str(r100s, ".4f"),
            count_75_str=_mean_std_str(c75s, ".1f"),
            count_100_str=_mean_std_str(c100s, ".1f"),
            count_total_str=_mean_std_str(ctotals, ".1f"),
        ))

    mol_summaries: Dict[str, List[SummaryRow]] = defaultdict(list)
    for sr in summary_rows:
        mol_summaries[sr.molecule].append(sr)

    best_recall: Dict[str, float] = {}
    worst_recall: Dict[str, float] = {}
    for mol, srs in mol_summaries.items():
        means = [s.recall_mean for s in srs]
        best_recall[mol] = max(means)
        worst_recall[mol] = min(means)

    config_note = ", ".join(f"{k}={v}" for k, v in CONFIG_DESCRIPTIONS.items())
    lines = [
        r"% Requires: \usepackage[table]{xcolor}",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Ablation study results (mean $\pm$ std across attempts). "
        f"Configs: {config_note}. "
        r"\colorbox{green!25}{Best} and \colorbox{red!25}{worst} mean recall per molecule are highlighted.}",
        r"\label{tab:ablation_results}",
        r"\begin{tabular}{llrrrrrrrrr}",
        r"\toprule",
        r"Molecule & Config & Confidence & Recall & Precision & Mol Match & $\geq$75\% & \#$\geq$75\% & 100\% & \#100\% & \#Total \\",
        r"\midrule",
    ]

    prev_molecule = None
    for sr in summary_rows:
        if prev_molecule is not None and sr.molecule != prev_molecule:
            lines.append(r"\midrule")

        conf_str = f"{sr.confidence:.2f}" if sr.confidence is not None else "--"
        recall_cell = sr.recall_str
        if best_recall[sr.molecule] != worst_recall[sr.molecule]:
            if sr.recall_mean == best_recall[sr.molecule]:
                recall_cell = r"\cellcolor{green!25}" + recall_cell
            elif sr.recall_mean == worst_recall[sr.molecule]:
                recall_cell = r"\cellcolor{red!25}" + recall_cell

        lines.append(
            f"{sr.molecule} & {sr.config} & "
            f"{conf_str} & {recall_cell} & {sr.precision_str} & {sr.mol_match_str} & "
            f"{sr.recall_75pct_str} & {sr.count_75_str} & "
            f"{sr.recall_100pct_str} & {sr.count_100_str} & {sr.count_total_str} \\\\"
        )
        prev_molecule = sr.molecule

    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    latex_str = "\n".join(lines)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(latex_str)
    print(f"\nLaTeX table saved to: {output_path}")
    return latex_str


def generate_csv(rows: List[TableRow], output_path: str) -> str:
    """Generate a CSV of scores across models, molecules, and configs."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model", "molecule", "config", "iteration", "confidence",
        "recall", "precision", "mol_match",
        "recall_75pct", "count_75", "recall_100pct", "count_100", "count_total",
    ]
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "model": row.model,
                "molecule": row.molecule,
                "config": row.config,
                "iteration": row.iteration,
                "confidence": f"{row.confidence:.4f}" if row.confidence is not None else "",
                "recall": f"{row.recall_score:.4f}",
                "precision": f"{row.precision_score:.4f}" if row.precision_score is not None else "",
                "mol_match": f"{row.molecule_match:.1f}" if row.molecule_match is not None else "",
                "recall_75pct": f"{row.recall_75pct:.4f}" if row.recall_75pct is not None else "",
                "count_75": row.count_75 if row.count_75 is not None else "",
                "recall_100pct": f"{row.recall_100pct:.4f}" if row.recall_100pct is not None else "",
                "count_100": row.count_100 if row.count_100 is not None else "",
                "count_total": row.count_total if row.count_total is not None else "",
            })
    print(f"\nCSV saved to: {output_path}")
    return output_path


async def validate_single_file(
    network_file: str,
    reference_file: str,
    output_dir: str = None,
    verbose: bool = False,
    json_output: bool = False,
) -> dict:
    """Validate a single network file, producing a combined precision + recall JSON."""
    from agents.validators.validation_orchestrator import ValidationOrchestrator

    effective_output_dir = output_dir or "validation_reports"
    network_stem = Path(network_file).stem
    output_path = str(Path(effective_output_dir) / f"{network_stem}_validation.json")

    if Path(output_path).exists():
        print(f"\n  [CACHED] Validation already exists: {output_path}")
        with open(output_path, 'r') as f:
            report_data = json.load(f)
        precision_score = report_data.get("overall_precision_score", 0)
        recall_score = report_data.get("overall_recall_score", 0.0)
        molecule_stats = report_data.get("molecule_match", {})
        frac_75, frac_100, c75, c100, ctotal = compute_recall_thresholds(
            report_data.get("reaction_recall", []))
        return {
            "network_file": network_file,
            "output_path": output_path,
            "overall_score": precision_score,
            "recall_score": recall_score,
            "molecule_match_percent": molecule_stats.get("coverage_percent", 0.0),
            "recall_75pct": frac_75,
            "recall_100pct": frac_100,
            "count_75": c75,
            "count_100": c100,
            "count_total": ctotal,
            "passed": precision_score >= 0.5,
        }

    print(f"\nValidating: {network_file}")
    print(f"Reference:  {reference_file}")
    print(f"Output Dir: {output_dir}")
    print("-" * 60)

    orchestrator = ValidationOrchestrator(reference_path=reference_file, output_dir=effective_output_dir)
    output_path = await orchestrator.validate_and_save(synthesis_file=network_file, output_dir=output_dir)

    with open(output_path, 'r') as f:
        report_data = json.load(f)

    molecule_stats = compute_molecule_statistics(network_file, reference_file)
    recall_data = compute_chemorigin_recall(network_file, reference_file)

    report_data["molecule_match"] = molecule_stats
    report_data["overall_recall_score"] = recall_data["average_recall_score"]
    report_data["reaction_recall"] = recall_data["reaction_recall"]
    report_data["total_reference_reactions"] = recall_data["total_reference_reactions"]
    report_data["total_network_reactions"] = recall_data["total_network_reactions"]

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2)

    precision_score = report_data.get("overall_precision_score", 0)
    recall_score = recall_data["average_recall_score"]

    if not json_output:
        print(f"\nPrecision: {precision_score:.2f}")
        print(f"Recall: {recall_score:.4f}")
        print(f"\nValidation report saved to: {output_path}")

    if verbose and not json_output:
        from models.validator_schemas import ValidationReport
        report = ValidationReport(**{k: v for k, v in report_data.items()
                                     if k in ValidationReport.model_fields})
        orchestrator.print_summary(report)
        print_molecule_statistics(molecule_stats)
        print_chemorigin_recall(recall_data)

    frac_75, frac_100, c75, c100, ctotal = compute_recall_thresholds(recall_data["reaction_recall"])

    return {
        "network_file": network_file,
        "output_path": output_path,
        "overall_score": precision_score,
        "recall_score": recall_score,
        "molecule_match_percent": molecule_stats["coverage_percent"],
        "recall_75pct": frac_75,
        "recall_100pct": frac_100,
        "count_75": c75,
        "count_100": c100,
        "count_total": ctotal,
        "passed": precision_score >= 0.5,
    }


def discover_molecules(model_dir: str) -> List[str]:
    """Auto-discover molecule names from filenames in a model directory."""
    files = glob.glob(f"{model_dir}/network_*_run*.json")
    configs_by_length = sorted(VALIDATION_CONFIGS, key=len, reverse=True)

    molecules = set()
    for f in files:
        remainder = Path(f).name[len("network_"):]
        m = re.search(r'_(\d{8}_\d{6})_', remainder)
        if m:
            molecules.add(remainder[:m.start()])
            continue
        for cfg in configs_by_length:
            idx = remainder.find(f"_{cfg}_run")
            if idx > 0:
                molecules.add(remainder[:idx])
                break
    return sorted(molecules)


def _clear_validation_cache(output_base: str) -> int:
    """Delete every cached *_validation.json under output_base. Returns count removed."""
    base = Path(output_base)
    if not base.exists():
        return 0
    removed = 0
    for cached in base.rglob("*_validation.json"):
        try:
            cached.unlink()
            removed += 1
        except OSError:
            pass
    return removed


async def cmd_validate(args) -> int:
    """Validate generated networks against ChemOrigins reference data."""
    input_base = "outputs_inchi_corrected"
    output_base = "validation_report"

    if not Path(input_base).exists():
        print(f"ERROR: {input_base}/ does not exist — run `inchi` first.")
        return 1

    if args.rebuild_cache:
        n = _clear_validation_cache(output_base)
        print(f"\n[--rebuild-cache] Removed {n} cached validation files under {output_base}")

    provider = getattr(args, "provider", None)
    if provider:
        model_dirs = [provider] if (Path(input_base) / provider).is_dir() else []
        if not model_dirs:
            print(f"ERROR: {input_base}/{provider}/ not found.")
            return 1
    else:
        model_dirs = sorted(d.name for d in Path(input_base).iterdir() if d.is_dir())

    print("\n" + "=" * 70)
    print("Network Validator (ChemOrigins) — Multi-Model Ablation Study")
    print("  All reactions validated against ChemOrigins reference")
    print("  Scoring: DRFP Tanimoto similarity (Probst et al. 2022)")
    print(f"  Models:  {', '.join(model_dirs)}")
    print(f"  Configs: {', '.join(VALIDATION_CONFIGS)}")
    print("=" * 70)

    global_results = []
    global_table_rows: List[TableRow] = []

    for model in model_dirs:
        model_input_dir = f"{input_base}/{model}"
        output_dir = f"{output_base}/{model}"

        raw_molecules = discover_molecules(model_input_dir)
        target_molecules = [m.replace("_", "-") for m in raw_molecules]

        print(f"\n{'=' * 70}")
        print(f"MODEL: {model}")
        print(f"  Molecules: {', '.join(target_molecules)}")
        print(f"  Input:     {model_input_dir}")
        print(f"  Output:    {output_dir}")
        print(f"{'=' * 70}")

        all_attempt_scores: Dict[str, Dict[str, list]] = {}
        table_rows: List[TableRow] = []
        results = []

        for molecule in target_molecules:
            print(f"\n{'#' * 70}")
            print(f"# MOLECULE: {molecule}")
            print(f"{'#' * 70}")
            all_attempt_scores[molecule] = {}

            for config in VALIDATION_CONFIGS:
                print(f"\n  {'~' * 60}")
                print(f"  config_{config}")
                print(f"  {'~' * 60}")

                attempt_files, final_file, reference_file = discover_files(
                    molecule, config, model_dir=model_input_dir)

                if not reference_file:
                    print(f"  No reference file found for {molecule}, skipping molecule")
                    break
                if not final_file and not attempt_files:
                    print(f"  No output files for {molecule} config_{config}, skipping config")
                    continue

                print(f"  Scoring {len(attempt_files)} attempts ...")
                attempt_scores = score_attempts(molecule, attempt_files, final_file, reference_file)

                enriched_scores = []
                for i, (label, recall, conf, r75, r100, c75, c100, ctotal) in enumerate(attempt_scores):
                    precision = None
                    mol_match = None
                    attempt_path = attempt_files[i] if i < len(attempt_files) else None
                    if attempt_path:
                        try:
                            val_result = await validate_single_file(
                                network_file=attempt_path,
                                reference_file=reference_file,
                                output_dir=output_dir,
                                verbose=False,
                                json_output=True,
                            )
                            precision = val_result.get("overall_score")
                            mol_match = val_result.get("molecule_match_percent")
                            results.append(val_result)
                        except Exception as e:
                            print(f"    Warning: validation failed for {attempt_path}: {e}")

                    enriched_scores.append((label, recall, conf, precision, mol_match))

                    conf_str = f"{conf:.2f}" if conf is not None else "N/A"
                    prec_str = f"{precision:.2f}" if precision is not None else "N/A"
                    mm_str = f"{mol_match:.1f}%" if mol_match is not None else "N/A"
                    print(f"    {label}: recall={recall:.4f}, precision={prec_str}, confidence={conf_str}, "
                          f"mol_match={mm_str}, >=75%={r75:.4f}({c75}/{ctotal}), 100%={r100:.4f}({c100}/{ctotal})")

                    match = re.search(r'(\d+)', label)
                    iteration = match.group(1) if match else label
                    table_rows.append(TableRow(
                        model=model, molecule=molecule, config=config, iteration=iteration,
                        confidence=conf, recall_score=recall, precision_score=precision,
                        molecule_match=mol_match, recall_75pct=r75, recall_100pct=r100,
                        count_75=c75, count_100=c100, count_total=ctotal,
                    ))

                all_attempt_scores[molecule][config] = enriched_scores

                if final_file:
                    try:
                        result = await validate_single_file(
                            network_file=final_file,
                            reference_file=reference_file,
                            output_dir=output_dir,
                            verbose=True,
                            json_output=False,
                        )
                        results.append(result)

                        table_rows.append(TableRow(
                            model=model, molecule=molecule, config=config, iteration="Final",
                            confidence=extract_overall_confidence(final_file),
                            recall_score=result.get("recall_score", 0.0),
                            precision_score=result.get("overall_score"),
                            molecule_match=result.get("molecule_match_percent"),
                            recall_75pct=result.get("recall_75pct"),
                            recall_100pct=result.get("recall_100pct"),
                            count_75=result.get("count_75"),
                            count_100=result.get("count_100"),
                            count_total=result.get("count_total"),
                        ))
                    except Exception as e:
                        print(f"\n  Error validating {final_file}: {e}")
                        import traceback
                        traceback.print_exc()
                        results.append({"network_file": final_file, "error": str(e), "passed": False})

        if all_attempt_scores:
            plot_attempt_scores(all_attempt_scores, f"{output_dir}/attempt_scores.png")
        if table_rows:
            generate_latex_table(table_rows, f"{output_dir}/ablation_results.tex")
            generate_csv(table_rows, f"{output_dir}/scores.csv")
            global_table_rows.extend(table_rows)

        print(f"\n  --- {model} summary ---")
        passed = sum(1 for r in results if r.get("passed", False))
        print(f"  Total Validated: {len(results)}, Passed: {passed}, Failed: {len(results) - passed}")
        global_results.extend(results)

    if global_table_rows:
        generate_csv(global_table_rows, f"{output_base}/scores.csv")

    print("\n" + "=" * 70)
    print("GLOBAL VALIDATION SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in global_results if r.get("passed", False))
    print(f"\nTotal Validated: {len(global_results)}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {len(global_results) - passed}")
    for r in global_results:
        status = "PASS" if r.get("passed") else "FAIL"
        print(f"  [{status}] {r['network_file']} (precision: {r.get('overall_score', 0):.2f}, "
              f"recall: {r.get('recall_score', 0):.4f})")

    return 0 if all(r.get("passed", False) for r in global_results) else 1


# ===========================================================================
# Stage: all (generate -> inchi -> validate)
# ===========================================================================

async def cmd_all(args) -> int:
    """Run generate -> inchi -> validate in sequence for one provider."""
    rc = await cmd_generate(args)
    if rc:
        return rc
    rc = cmd_inchi(args)
    if rc:
        return rc
    return await cmd_validate(args)


# ===========================================================================
# CLI
# ===========================================================================

def _add_generate_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--molecules", help=f"comma-separated molecules (default: {','.join(DEFAULT_MOLECULES)})")
    p.add_argument("--configs", help=f"comma-separated ablation configs (default: {','.join(DEFAULT_GENERATE_CONFIGS)}). "
                                      f"Available: {', '.join(ABLATION_CONFIGS)}")
    p.add_argument("--runs", type=int, default=1, help="runs per config (default: 1)")
    p.add_argument("--confidence-threshold", type=float, default=0.9, help="min confidence to accept (default: 0.9)")
    p.add_argument("--max-retries", type=int, default=3, help="critic retries per run (default: 3)")
    p.add_argument("--num-pathways", type=int, default=10, help="pathways to generate (default: 10)")
    p.add_argument("--no-io-logging", dest="io_logging", action="store_false", help="disable JSONL I/O logging")
    p.set_defaults(io_logging=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.py",
        description="Astra ablation pipeline: generate -> inchi -> validate.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="{generate,inchi,validate,all}")

    g = sub.add_parser("generate", help="generate synthesis networks (outputs/{provider}/)")
    g.add_argument("--provider", help="model provider / output subfolder (overrides MODEL_PROVIDER)")
    _add_generate_args(g)

    i = sub.add_parser("inchi", help="backfill InChI from PubChem (outputs_inchi_corrected/{provider}/)")
    i.add_argument("--provider", help="restrict to one provider subfolder (default: all)")

    v = sub.add_parser("validate", help="validate networks vs ChemOrigins (validation_report/{provider}/)")
    v.add_argument("--provider", help="restrict to one provider subfolder (default: all)")
    v.add_argument("--rebuild-cache", action="store_true", help="delete cached *_validation.json before validating")

    a = sub.add_parser("all", help="run generate -> inchi -> validate for one provider")
    a.add_argument("--provider", help="model provider / output subfolder (overrides MODEL_PROVIDER)")
    a.add_argument("--rebuild-cache", action="store_true", help="delete cached *_validation.json before validating")
    _add_generate_args(a)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.command:
        build_parser().print_help()
        return 1
    if args.command == "generate":
        return asyncio.run(cmd_generate(args))
    if args.command == "inchi":
        return cmd_inchi(args)
    if args.command == "validate":
        return asyncio.run(cmd_validate(args))
    if args.command == "all":
        return asyncio.run(cmd_all(args))
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
