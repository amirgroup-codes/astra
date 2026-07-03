"""
Pydantic models for molecular synthesis reactions and evaluations.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class Molecule(BaseModel):
    """Model for a molecule with detailed chemical identifiers."""
    formula: str = Field(..., description="Chemical formula (e.g., CH4, H2O)")
    iupac_name: str = Field(..., description="IUPAC systematic name")
    inchi: Optional[str] = Field(None, description="International Chemical Identifier (InChI)")
    common_name: Optional[str] = Field(None, description="Common/trivial name (e.g., Methane for CH4)")


class ReactionStep(BaseModel):
    """Model for a single chemical reaction step."""
    step: int = Field(..., description="Step number in the synthesis pathway (1-10)")
    step_id: Optional[str] = Field(None, description="Unique step identifier from synthesis plan (e.g., 'A1', 'B1', 'C1')")
    branch_id: Optional[str] = Field(None, description="Branch this step belongs to in the synthesis DAG (e.g., 'A', 'B', 'main')")
    reactants: List[Molecule] = Field(..., description="List of reactant molecules with full details")
    product: Molecule = Field(..., description="Product molecule with full details")
    reaction: str = Field(..., description="Reaction equation in format 'A + B -> C'")
    conditions: Dict[str, Any] = Field(
        ...,
        description="Reaction conditions (environment, temperature, pressure, UV exposure, catalyst, etc.)"
    )
    reasoning: str = Field(
        ...,
        description="Detailed explanation of why this reaction makes sense in the context of prebiotic chemistry"
    )
    confidence: Optional[float] = Field(
        None,
        description="Agent's self-assessed confidence (0-1), set after evaluation"
    )
    selected_agent: Optional[str] = Field(
        None,
        description="The agent type that proposed this reaction (Hydrothermal, Surface, or Biochemical)"
    )


class CriticEvaluation(BaseModel):
    """Model for critic's evaluation of a proposed reaction."""
    chemical_feasibility: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score for chemical feasibility of the reaction (0-1)"
    )
    conditions_appropriateness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score for appropriateness of prebiotic geochemical conditions (0-1)"
    )
    temperature_feasibility: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score for temperature feasibility in given environment (0-1)"
    )
    pressure_feasibility: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score for pressure feasibility in given environment (0-1)"
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score for this reaction (0-1)"
    )
    feedback: str = Field(
        ...,
        description="Detailed feedback explaining the evaluation and any concerns"
    )
    approved: bool = Field(
        ...,
        description="Whether this reaction is approved (confidence >= 0.8)"
    )
    suggestions: Optional[List[str]] = Field(
        default=None,
        description="Specific suggestions for improvement if not approved"
    )

    @field_validator('suggestions', mode='before')
    @classmethod
    def convert_suggestions_to_strings(cls, v):
        """Convert dict suggestions to strings if LLM returns structured format."""
        if v is None:
            return v
        if not isinstance(v, list):
            return v
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                # Handle {"area": "...", "description": "..."} format
                area = item.get('area', '')
                desc = item.get('description', item.get('suggestion', ''))
                if area and desc:
                    result.append(f"{area}: {desc}")
                elif desc:
                    result.append(desc)
                elif area:
                    result.append(area)
                else:
                    # Fallback: convert entire dict to string
                    result.append(str(item))
            else:
                result.append(str(item))
        return result


class SynthesisResult(BaseModel):
    """Complete synthesis pathway result."""
    target_molecule: str
    accepted_reactions: List[ReactionStep]
    total_steps: int
    success: bool
    notes: Optional[str] = None


class Citation(BaseModel):
    """A citation from deep research."""
    title: str = Field(..., description="Title of the cited work")
    url: str = Field(..., description="URL to the source")


class DeepResearchReport(BaseModel):
    """Report from the AstroDeepResearchAgent."""
    query: str = Field(..., description="The research query submitted")
    findings: str = Field(..., description="Full text of the research report")
    citations: List[Citation] = Field(default_factory=list, description="List of citations")
    research_successful: bool = Field(default=True, description="Whether research completed successfully")
    error_message: Optional[str] = Field(default=None, description="Error message if research failed")


class EnrichedProposal(BaseModel):
    """Proposal with original and final reactions."""
    original_reaction: "ReactionStep" = Field(
        ..., description="The original proposed reaction"
    )
    final_reaction: "ReactionStep" = Field(
        ..., description="The final reaction (may be revised from original)"
    )


# Update forward references for EnrichedProposal
EnrichedProposal.model_rebuild()


# ============================================================
# Completion Assessment Model (for dynamic workflow)
# ============================================================

class CompletionAssessment(BaseModel):
    """Assessment of whether the synthesis pathway is complete."""
    is_complete: bool = Field(
        ...,
        description="Whether the synthesis pathway has achieved its goal"
    )
    reasoning: str = Field(
        ...,
        description="Explanation for why the pathway is/isn't complete"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the completion assessment (0-1)"
    )
    target_molecule_achieved: bool = Field(
        default=False,
        description="Whether the exact target molecule (or close precursor) was synthesized"
    )
    pathway_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall quality score of the synthesis pathway (0-1)"
    )
    suggested_next_environment: Optional[str] = Field(
        default=None,
        description="If not complete, which environment to use next (Hydrothermal/Surface/Biochemical)"
    )
    suggested_next_step: Optional[str] = Field(
        default=None,
        description="If not complete, a brief suggestion for the next reaction"
    )
