"""
Pydantic models for bipartite graph synthesis networks.

The network consists of two node types:
- Molecule nodes: Chemical species (substrates, products, intermediates)
- Reaction nodes: Chemical transformations connecting molecules
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NetworkMolecule(BaseModel):
    """Molecule node in the bipartite synthesis network."""
    id: str = Field(..., description="Unique molecule ID (e.g., 'mol_001')")
    formula: str = Field(..., description="Chemical formula")
    iupac_name: str = Field(..., description="IUPAC systematic name")
    common_name: Optional[str] = Field(None, description="Common name")
    inchi: Optional[str] = Field(None, description="InChI identifier")
    role: str = Field(
        ..., description="Role in the network"
    )
    environment_formed: Optional[str] = Field(
        None, description="Environment where this molecule is formed"
    )


class NetworkReaction(BaseModel):
    """Reaction node in the bipartite synthesis network."""
    id: str = Field(..., description="Unique reaction ID (e.g., 'rxn_001')")
    name: str = Field(..., description="Descriptive reaction name")
    inputs: List[str] = Field(..., description="Input molecule IDs (reactants)")
    outputs: List[str] = Field(..., description="Output molecule IDs (products)")
    environment: str = Field(
        ..., description="Environment where reaction occurs"
    )
    agents: Optional[List[Optional[str]]] = Field(
        default=None,
        description="Mineral catalysts or agents involved (e.g., Greigite, Magnetite, Pyrite, Elemental Iron)"
    )
    conditions: Dict[str, Any] = Field(
        default_factory=dict, description="Reaction conditions"
    )
    mechanism: str = Field(..., description="Reaction mechanism description")
    reasoning: str = Field(..., description="Scientific justification")


class ConvergencePoint(BaseModel):
    """A hub molecule where multiple pathways converge."""
    molecule_id: str = Field(..., description="ID of the hub molecule")
    incoming_reactions: List[str] = Field(
        default_factory=list, description="Reaction IDs that produce this molecule"
    )
    outgoing_reactions: List[str] = Field(
        default_factory=list, description="Reaction IDs that consume this molecule"
    )


class SynthesisPathway(BaseModel):
    """A named pathway through the network."""
    pathway_id: str = Field(..., description="Unique pathway ID (e.g., 'P1')")
    name: str = Field(..., description="Descriptive pathway name")
    description: str = Field(..., description="Pathway description")
    reaction_sequence: List[str] = Field(
        ..., description="Ordered list of reaction IDs in this pathway"
    )
    key_intermediates: List[str] = Field(
        default_factory=list, description="Key intermediate molecule IDs"
    )


class SynthesisNetwork(BaseModel):
    """Complete bipartite synthesis network output from SynthesisNetworkAgent."""
    target_molecule: str = Field(..., description="Target molecule to synthesize")
    overall_strategy: str = Field(..., description="High-level synthesis strategy")

    # Bipartite graph nodes
    molecules: List[NetworkMolecule] = Field(
        ..., description="All molecule nodes in the network"
    )
    reactions: List[NetworkReaction] = Field(
        ..., description="All reaction nodes in the network"
    )

    # Pathway analysis
    pathways: List[SynthesisPathway] = Field(
        ..., description="Named pathways through the network"
    )
    hub_molecules: List[str] = Field(
        default_factory=list, description="IDs of hub intermediate molecules"
    )
    convergence_points: List[ConvergencePoint] = Field(
        default_factory=list, description="Points where pathways converge"
    )

    def get_molecule(self, mol_id: str) -> Optional[NetworkMolecule]:
        """Get a molecule by ID."""
        for mol in self.molecules:
            if mol.id == mol_id:
                return mol
        return None

    def get_reaction(self, rxn_id: str) -> Optional[NetworkReaction]:
        """Get a reaction by ID."""
        for rxn in self.reactions:
            if rxn.id == rxn_id:
                return rxn
        return None

    def get_pathway(self, pathway_id: str) -> Optional[SynthesisPathway]:
        """Get a pathway by ID."""
        for p in self.pathways:
            if p.pathway_id == pathway_id:
                return p
        return None

    @property
    def molecule_count(self) -> int:
        """Total number of molecules in the network."""
        return len(self.molecules)

    @property
    def reaction_count(self) -> int:
        """Total number of reactions in the network."""
        return len(self.reactions)


class PathwayEvaluation(BaseModel):
    """Critic evaluation of a single synthesis pathway."""
    pathway_id: str = Field(..., description="ID of the evaluated pathway")

    # Per-reaction scores
    reaction_scores: Dict[str, float] = Field(
        default_factory=dict, description="Map of reaction_id to confidence score"
    )

    # Pathway-level scores
    chemical_feasibility: float = Field(..., ge=0.0, le=1.0)
    pathway_coherence: float = Field(..., ge=0.0, le=1.0)
    environmental_progression: float = Field(..., ge=0.0, le=1.0)
    target_achievement: float = Field(..., ge=0.0, le=1.0)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)

    feedback: str = Field(..., description="Detailed evaluation feedback")
    approved: bool = Field(..., description="Whether pathway meets threshold")

    problematic_reactions: List[str] = Field(
        default_factory=list, description="Reaction IDs with low scores"
    )
    suggestions: List[str] = Field(
        default_factory=list, description="Improvement suggestions"
    )


class NetworkEvaluation(BaseModel):
    """Critic evaluation of entire synthesis network."""
    target_molecule: str = Field(..., description="Target molecule")

    # Per-pathway evaluations
    pathway_evaluations: List[PathwayEvaluation] = Field(
        default_factory=list, description="Evaluations for each pathway"
    )

    # Network-level assessment
    best_pathway_id: str = Field(..., description="ID of highest-scoring pathway")
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    network_feedback: str = Field(..., description="Overall network assessment")
    approved: bool = Field(..., description="At least one pathway approved")

    # Network topology assessment
    hub_quality: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Quality of hub molecule selection"
    )
    convergence_quality: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Quality of pathway convergence"
    )


class NetworkSynthesisResult(BaseModel):
    """Final result from NetworkSynthesisWorkflow."""
    target_molecule: str = Field(..., description="Target molecule")
    network: SynthesisNetwork = Field(..., description="Generated synthesis network")
    evaluation: NetworkEvaluation = Field(..., description="Critic evaluation")
    success: bool = Field(..., description="Whether synthesis was approved")
    attempts: int = Field(..., description="Number of attempts made")
    notes: Optional[str] = Field(None, description="Additional notes")


