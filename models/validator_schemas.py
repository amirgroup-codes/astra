"""
Pydantic models for ChemOrigins reference validation.
"""
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


# =============================================================================
# Pathway Match Models
# =============================================================================

class ReferenceCitation(BaseModel):
    """A citation from the ChemOrigins reference."""
    title: str = Field(..., description="Title of the cited work")
    authors: str = Field(..., description="Authors of the cited work")
    journal: str = Field(..., description="Journal name")
    year: int = Field(..., description="Publication year")
    doi: Optional[str] = Field(None, description="DOI if available")


class PathwayMatch(BaseModel):
    """Result of matching a reaction to reference pathways."""
    match_type: Literal["exact", "similar", "partial", "none"] = Field(
        ...,
        description="Type of match found"
    )
    matched_reaction_key: Optional[str] = Field(
        None,
        description="Key of the matched reference reaction (e.g., 'pbr-000087')"
    )
    matched_reaction_smiles: Optional[str] = Field(
        None,
        description="SMILES of the matched reference reaction"
    )
    drfp_similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="DRFP Tanimoto similarity to the reference reaction (0-1)"
    )
    supporting_citations: List[ReferenceCitation] = Field(
        default_factory=list,
        description="Citations supporting this reaction"
    )
    match_details: str = Field(
        default="",
        description="Details about how the match was determined"
    )


class PathwayMatchResult(BaseModel):
    """Result from PathwayMatchValidator."""
    step: int = Field(..., description="Step number being validated")
    reaction_string: str = Field(..., description="The reaction being validated")
    matches: List[PathwayMatch] = Field(
        default_factory=list,
        description="List of potential pathway matches"
    )
    best_match: Optional[PathwayMatch] = Field(
        None,
        description="The best matching reference pathway"
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Pathway match score (0-1)"
    )
    reference_recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations from reference data"
    )


# =============================================================================
# Overall Validation Models
# =============================================================================

class ReactionValidation(BaseModel):
    """Complete validation result for a single reaction step."""
    step: int = Field(..., description="Step number")
    reaction_string: str = Field(..., description="The reaction string")
    selected_agent: Optional[str] = Field(
        None,
        description="Agent type that proposed this reaction (Hydrothermal, Surface, Biochemical)"
    )
    validation_type: Literal["pathway"] = Field(
        default="pathway",
        description="Type of validation performed"
    )
    pathway_match: Optional[PathwayMatchResult] = Field(
        None,
        description="Pathway match validation result (for ParentBody)"
    )
    weighted_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Weighted overall score for this step"
    )
    all_issues: List[str] = Field(
        default_factory=list,
        description="All issues from all validators"
    )
    is_valid: bool = Field(
        default=True,
        description="Whether the step passes validation"
    )


class ValidationReport(BaseModel):
    """Complete validation report for a synthesis pathway."""
    target_molecule: str = Field(..., description="Target molecule of the synthesis")
    reference_file: str = Field(..., description="Path to the reference file used")
    reference_module_key: Optional[str] = Field(
        None,
        description="Key of the reference module (e.g., 'pbmdl-000001')"
    )
    reference_module_name: Optional[str] = Field(
        None,
        description="Name of the reference module (e.g., 'Alanine-synthesis')"
    )

    # Overall scores
    overall_precision_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall alignment score (weighted average)"
    )

    # Individual validator scores
    validator_scores: Dict[str, float] = Field(
        ...,
        description="Scores from each validator"
    )

    # Per-reaction validations
    reaction_validations: List[ReactionValidation] = Field(
        ...,
        description="Validation results for each reaction step"
    )

    # Issues and recommendations
    critical_issues: List[str] = Field(
        default_factory=list,
        description="Critical issues that invalidate the synthesis"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-critical warnings"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for improvement"
    )

    # Reference pathway information
    reference_pathways_matched: List[str] = Field(
        default_factory=list,
        description="Keys of reference pathways that were matched"
    )
    reference_pathways_available: List[str] = Field(
        default_factory=list,
        description="Keys of all available reference pathways"
    )

    # Molecule match statistics
    molecule_match: Optional[Dict[str, Any]] = Field(
        None,
        description="Molecule match statistics comparing output molecules to reference molecules"
    )

    # Metadata
    validation_timestamp: str = Field(..., description="Timestamp of validation")
    synthesis_file: str = Field(..., description="Path to the synthesis file validated")
