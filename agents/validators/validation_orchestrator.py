"""
ValidationOrchestrator: Coordinates pathway validation and produces validation reports.

Validates ALL synthesis reactions against ChemOrigins reference data using
embedding similarity and InChI comparison.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from core.chemorigins_loader import ChemOriginsLoader
from models.validator_schemas import (
    ValidationReport,
    ReactionValidation,
    PathwayMatchResult,
    PathwayMatch
)
from agents.validators.chemorigins_validator import ChemOriginsValidator


class ValidationOrchestrator:
    """
    Orchestrator that validates ALL synthesis reactions against ChemOrigins.

    Uses embedding similarity to find matching reference reactions,
    then InChI comparison for precise molecular similarity scoring.
    """

    def __init__(
        self,
        reference_path: str,
        output_dir: str = "validation_reports"
    ):
        """
        Initialize the ValidationOrchestrator.

        Args:
            reference_path: Path to the ChemOrigins reference JSON file
            output_dir: Directory for validation reports
        """
        self.reference_path = reference_path
        self.output_dir = output_dir

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Load reference data
        self.reference_loader = ChemOriginsLoader(reference_path)
        self.reference_loader.load()

        # Validator will be initialized when we know the synthesis file
        self.chemorigins_validator: Optional[ChemOriginsValidator] = None

    def _init_validators(self):
        """Initialize validators."""
        self.chemorigins_validator = ChemOriginsValidator(self.reference_loader, None)

    def _parse_network_format(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transform network format reactions to validator-compatible format.

        The network format uses molecule IDs (e.g., "mol_005") as references.
        This method resolves those IDs to actual molecule objects with InChI.

        Args:
            data: Network format data with "network" key

        Returns:
            List of reaction dicts compatible with ChemOriginsValidator
        """
        network = data.get("network", {})
        molecules = {m["id"]: m for m in network.get("molecules", [])}

        transformed_reactions = []
        for idx, rxn in enumerate(network.get("reactions", []), 1):
            # Resolve input molecule IDs to molecule objects
            reactants = [molecules[mid] for mid in rxn.get("inputs", []) if mid in molecules]

            # Resolve output molecule IDs - include all products (including byproducts)
            outputs = [molecules[mid] for mid in rxn.get("outputs", []) if mid in molecules]

            # Build reaction string from formulas
            reactant_formulas = " + ".join(r.get("formula", "?") for r in reactants)
            product_formulas = " + ".join(o.get("formula", "?") for o in outputs)
            reaction_string = f"{reactant_formulas} -> {product_formulas}"

            transformed_reactions.append({
                "step": idx,
                "reaction": reaction_string,
                "reaction_id": rxn.get("id"),
                "reaction_name": rxn.get("name"),
                "selected_agent": rxn.get("environment"),  # Map environment to selected_agent
                "reactants": reactants,
                "products": outputs,  # All products including byproducts
                "conditions": rxn.get("conditions", {})
            })

        return transformed_reactions

    async def validate_synthesis(
        self,
        synthesis_data: Dict[str, Any],
        synthesis_file: str
    ) -> ValidationReport:
        """
        Validate a complete synthesis pathway against ChemOrigins.

        All reactions (regardless of which agent proposed them) are validated
        against the ChemOrigins reference using embedding similarity and
        InChI comparison.

        Args:
            synthesis_data: The synthesis output to validate
            synthesis_file: Path to the synthesis file

        Returns:
            ValidationReport: Complete validation report
        """
        # Initialize validators
        self._init_validators()

        target_molecule = synthesis_data.get("target_molecule", "Unknown")

        # Detect format: network format has "network" key
        if "network" in synthesis_data:
            reactions = self._parse_network_format(synthesis_data)
        else:
            # Legacy synthesis format
            reactions = synthesis_data.get("reactions", [])

        # Validate each reaction
        reaction_validations: List[ReactionValidation] = []
        all_recommendations: List[str] = []
        matched_pathways: List[str] = []

        # Track scores
        chemorigins_scores: List[float] = []

        for reaction in reactions:
            step = reaction.get("step", 0)
            selected_agent = reaction.get("selected_agent", "")
            reaction_string = reaction.get("reaction", "")

            # Validate ALL reactions against ChemOrigins
            pathway_result = await self.chemorigins_validator.validate(reaction, step)

            rxn_validation = ReactionValidation(
                step=step,
                reaction_string=reaction_string,
                selected_agent=selected_agent,
                validation_type="pathway",
                pathway_match=pathway_result,
                weighted_score=pathway_result.score,
                all_issues=[f"ChemOrigins: {r}" for r in pathway_result.reference_recommendations],
                is_valid=pathway_result.score >= 0.5
            )
            chemorigins_scores.append(pathway_result.score)

            # Collect matched pathways
            if pathway_result.best_match and pathway_result.best_match.matched_reaction_key:
                if pathway_result.best_match.matched_reaction_key not in matched_pathways:
                    matched_pathways.append(pathway_result.best_match.matched_reaction_key)

            # Collect recommendations
            for rec in pathway_result.reference_recommendations:
                if rec not in all_recommendations:
                    all_recommendations.append(rec)

            reaction_validations.append(rxn_validation)

        # Calculate overall score
        overall_score = sum(chemorigins_scores) / len(chemorigins_scores) if chemorigins_scores else 0.0

        # Get reference info
        ref_summary = self.reference_loader.get_reference_summary()

        # Create validation report
        report = ValidationReport(
            target_molecule=target_molecule,
            reference_file=str(self.reference_path),
            reference_module_key=ref_summary.get("module_key"),
            reference_module_name=ref_summary.get("module_name"),
            overall_precision_score=round(overall_score, 2),
            validator_scores={
                "chemorigins": round(overall_score, 2)
            },
            reaction_validations=reaction_validations,
            critical_issues=[],
            warnings=[],
            recommendations=all_recommendations[:10],
            reference_pathways_matched=matched_pathways,
            reference_pathways_available=ref_summary.get("reaction_keys", []),
            validation_timestamp=datetime.now().isoformat(),
            synthesis_file=synthesis_file
        )

        return report

    async def validate_and_save(
        self,
        synthesis_file: str,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Load synthesis file, validate, and save report.

        Args:
            synthesis_file: Path to synthesis JSON file
            output_dir: Optional output directory (defaults to self.output_dir)

        Returns:
            str: Path to saved validation report
        """
        # Use class output_dir if not specified
        if output_dir is None:
            output_dir = self.output_dir

        # Load synthesis data
        with open(synthesis_file, 'r', encoding='utf-8') as f:
            synthesis_data = json.load(f)

        # Validate
        report = await self.validate_synthesis(synthesis_data, synthesis_file)

        # Determine output path
        synthesis_path = Path(synthesis_file)
        output_path = Path(output_dir) / f"{synthesis_path.stem}_validation.json"

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save report
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report.model_dump(), f, indent=2)

        return str(output_path)

    def print_summary(self, report: ValidationReport) -> None:
        """
        Print a human-readable summary of the validation report.

        Args:
            report: The validation report to summarize
        """
        print("\n" + "=" * 70)
        print("VALIDATION REPORT")
        print("=" * 70)

        print(f"\nTarget Molecule: {report.target_molecule}")
        print(f"Reference Module: {report.reference_module_name} ({report.reference_module_key})")
        print(f"Overall Precision Score: {report.overall_precision_score:.2f}")

        # Print validator scores
        print("\n--- Validator Scores ---")
        for validator, score in report.validator_scores.items():
            if score > 0:
                print(f"  {validator}: {score:.2f}")

        print("\n--- Per-Reaction Validation ---")
        for rv in report.reaction_validations:
            status = "PASS" if rv.is_valid else "FAIL"

            print(f"\nStep {rv.step}: {status} (score: {rv.weighted_score:.2f})")
            print(f"  Agent: {rv.selected_agent or 'Unknown'}")
            print(f"  Reaction: {rv.reaction_string[:80]}{'...' if len(rv.reaction_string) > 80 else ''}")

            if rv.pathway_match:
                print(f"  ChemOrigins Match: {rv.pathway_match.score:.2f}")
                if rv.pathway_match.best_match:
                    print(f"  Matched Ref: {rv.pathway_match.best_match.matched_reaction_key}")
                    details = rv.pathway_match.best_match.match_details[:80]
                    print(f"  Details: {details}{'...' if len(rv.pathway_match.best_match.match_details) > 80 else ''}")

        if report.recommendations:
            print("\n--- Recommendations ---")
            for rec in report.recommendations[:5]:
                print(f"  * {rec[:100]}{'...' if len(rec) > 100 else ''}")

        print("\n" + "=" * 70)
        print(f"Validation completed: {report.validation_timestamp}")
        print("=" * 70 + "\n")
