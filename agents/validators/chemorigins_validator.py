"""
ChemOriginsValidator: Validates synthesis reactions against ChemOrigins reference data.

Computes InChI similarity for ALL reference reactions and selects the best match
by highest average of product and reactant similarity.
"""
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from core.chemorigins_loader import ChemOriginsLoader, ReferenceReaction
from models.validator_schemas import (
    PathwayMatchResult,
    PathwayMatch,
    ReferenceCitation
)

if TYPE_CHECKING:
    from core.validation_io_logger import ValidationIOLogger


class ChemOriginsValidator:
    """
    Validates synthesis reactions against ChemOrigins reference data.

    Computes InChI similarity for all reference reactions and selects the
    best match by highest average of product and reactant similarity.
    """

    def __init__(
        self,
        reference_loader: ChemOriginsLoader,
        io_logger: Optional["ValidationIOLogger"] = None
    ):
        """
        Initialize the ChemOriginsValidator.

        Args:
            reference_loader: Loaded ChemOrigins reference data
            io_logger: Optional logger for I/O
        """
        self.reference_loader = reference_loader
        self.io_logger = io_logger

        # Build reaction lookup by key
        self._reactions_by_key: Dict[str, ReferenceReaction] = {}
        if reference_loader.module:
            for rxn in reference_loader.module.reactions:
                self._reactions_by_key[rxn.key] = rxn

    async def validate(self, reaction: Dict[str, Any], step: int) -> PathwayMatchResult:
        """
        Validate a reaction against ChemOrigins reference data.

        Computes DRFP Tanimoto similarity for ALL reference reactions and selects
        the highest-scoring one as the best match.

        Args:
            reaction: The reaction to validate
            step: Step number

        Returns:
            PathwayMatchResult: Validation result with best match by DRFP similarity
        """
        reaction_string = reaction.get("reaction", "")

        # Compute DRFP similarity for ALL reference reactions
        # Store tuples of (PathwayMatch, drfp_score)
        match_data: List[Tuple[PathwayMatch, float]] = []

        for reaction_key, ref_rxn in self._reactions_by_key.items():
            match, drfp_score = self._compute_inchi_match(
                reaction, ref_rxn, reaction_key
            )
            match_data.append((match, drfp_score))

        # Handle no matches case (empty reference database)
        if not match_data:
            return PathwayMatchResult(
                step=step,
                reaction_string=reaction_string,
                matches=[],
                best_match=PathwayMatch(
                    match_type="none",
                    matched_reaction_key=None,
                    matched_reaction_smiles=None,
                    drfp_similarity=0.0,
                    supporting_citations=[],
                    match_details="No reference reactions available"
                ),
                score=0.0,
                reference_recommendations=["No ChemOrigins reference data available"]
            )

        # Select best match by highest DRFP similarity
        match_data.sort(key=lambda x: x[1], reverse=True)

        matches = [match for match, _ in match_data]
        best_match = matches[0]
        best_score = match_data[0][1]

        # Generate recommendations
        recommendations = self._generate_recommendations(reaction, best_match)

        return PathwayMatchResult(
            step=step,
            reaction_string=reaction_string,
            matches=matches[:5],  # Return top 5 matches
            best_match=best_match,
            score=best_score,
            reference_recommendations=recommendations
        )

    def _compute_inchi_match(
        self,
        reaction: Dict[str, Any],
        ref_rxn: ReferenceReaction,
        reaction_key: str
    ) -> Tuple[PathwayMatch, float]:
        """
        Compute DRFP similarity for a single reference reaction.

        Args:
            reaction: The proposed synthesis reaction
            ref_rxn: The reference reaction to compare
            reaction_key: Key of the reference reaction

        Returns:
            Tuple of (PathwayMatch, drfp_score)
        """
        from agents.validators.rdkit_similarity import compute_reaction_similarity

        drfp_score, _ = compute_reaction_similarity(reaction, ref_rxn)

        if drfp_score >= 0.95:
            match_type = "exact"
        elif drfp_score >= 0.5:
            match_type = "similar"
        elif drfp_score > 0:
            match_type = "partial"
        else:
            match_type = "none"

        citations = []
        for source in ref_rxn.sources:
            citations.append(ReferenceCitation(
                title=source.title,
                authors=source.authors,
                journal=source.journal,
                year=source.year,
                doi=source.doi
            ))

        pathway_match = PathwayMatch(
            match_type=match_type,
            matched_reaction_key=reaction_key,
            matched_reaction_smiles=ref_rxn.smiles,
            drfp_similarity=drfp_score,
            supporting_citations=citations,
            match_details=f"DRFP Tanimoto: {drfp_score:.3f}"
        )

        return pathway_match, drfp_score

    def _generate_recommendations(
        self,
        reaction: Dict[str, Any],
        best_match: PathwayMatch
    ) -> List[str]:
        """Generate recommendations based on match results."""
        recommendations = []

        if best_match.drfp_similarity < 0.5:
            recommendations.append(
                "Low similarity score. Consider reviewing the ChemOrigins reference "
                "for validated synthesis routes."
            )

        if best_match.matched_reaction_key:
            ref_rxn = self._reactions_by_key.get(best_match.matched_reaction_key)
            if ref_rxn:
                formatted = self.reference_loader.format_reaction_for_comparison(ref_rxn)
                recommendations.append(
                    f"Best match: {best_match.matched_reaction_key} - {formatted}"
                )

        return recommendations[:3]
