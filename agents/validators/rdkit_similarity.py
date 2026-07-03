"""
DRFP-based reaction similarity utilities for pathway validation.

Reactions are compared by encoding each as a Differential Reaction Fingerprint
(Probst, Schwaller & Reymond, Digital Discovery 2022) and measuring Tanimoto
similarity between the two binary fingerprints. Per-molecule InChI/Morgan
helpers are retained for the molecule-level coverage statistic computed
in pipeline.py's validate stage.
"""
from typing import Dict, Any, List, Optional, Tuple
import logging

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFingerprintGenerator, DataStructs
from drfp import DrfpEncoder

from core.chemorigins_loader import ReferenceReaction

# Suppress RDKit warnings
RDLogger.DisableLog('rdApp.*')

logger = logging.getLogger(__name__)

# Default similarity threshold for considering molecules as "same"
DEFAULT_SIMILARITY_THRESHOLD = 0.95

# DRFP encoding parameters (defaults from the DRFP package)
DRFP_N_BITS = 2048
DRFP_RADIUS = 3

# Morgan fingerprint generator (used by molecule-level coverage helpers below)
_morgan_gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def normalize_inchi(inchi: str) -> Optional[str]:
    """
    Normalize an InChI string for comparison.

    Strips whitespace and ensures consistent format without RDKit conversion.
    """
    if not inchi or not isinstance(inchi, str):
        return None

    inchi = inchi.strip()
    if not inchi.startswith("InChI"):
        return None

    return inchi


def compute_fingerprint_similarity(inchi1: str, inchi2: str) -> float:
    """
    Tanimoto similarity between two molecules using Morgan fingerprints
    (ECFP4-like, radius=2, 2048 bits).
    """
    try:
        mol1 = Chem.MolFromInchi(inchi1)
        mol2 = Chem.MolFromInchi(inchi2)

        if mol1 is None or mol2 is None:
            return 0.0

        fp1 = _morgan_gen.GetFingerprint(mol1)
        fp2 = _morgan_gen.GetFingerprint(mol2)

        return DataStructs.TanimotoSimilarity(fp1, fp2)
    except Exception:
        return 0.0


def compute_molecule_similarity(inchi1: str, inchi2: str) -> float:
    """
    Similarity between two molecules. Identical InChIs score 1.0; otherwise
    falls back to Morgan-Tanimoto. Used by the molecule-coverage statistic.
    """
    if not inchi1 or not inchi2:
        return 0.0

    norm1 = normalize_inchi(inchi1)
    norm2 = normalize_inchi(inchi2)

    if norm1 and norm2 and norm1 == norm2:
        return 1.0

    return compute_fingerprint_similarity(inchi1, inchi2)


def _inchi_to_smiles(inchi: Optional[str]) -> Optional[str]:
    """
    Convert an InChI string to canonical SMILES via RDKit, stripping stereo.

    Stereochemistry is dropped because the ChemOrigins reference reactions are
    written without stereo annotations; keeping stereo on the agent side would
    cause systematic DRFP penalties when the agent correctly identifies a
    specific enantiomer (e.g. L-alanine) but the reference is constitutional.
    """
    if not inchi:
        return None
    try:
        mol = Chem.MolFromInchi(inchi)
        if mol is None:
            return None
        return Chem.MolToSmiles(mol, isomericSmiles=False)
    except Exception:
        return None


def _strip_stereo_smiles(smiles: Optional[str]) -> Optional[str]:
    """Re-canonicalize a SMILES string with stereo annotations removed."""
    if not smiles:
        return None
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return Chem.MolToSmiles(mol, isomericSmiles=False)
    except Exception:
        return None


def _build_reaction_smiles(
    reactant_smiles: List[str],
    product_smiles: List[str]
) -> Optional[str]:
    """Build a reaction SMILES string of the form 'A.B>>C.D'."""
    reactants = [s for s in reactant_smiles if s]
    products = [s for s in product_smiles if s]
    if not reactants or not products:
        return None
    return f"{'.'.join(reactants)}>>{'.'.join(products)}"


def _tanimoto(fp1: np.ndarray, fp2: np.ndarray) -> float:
    """Tanimoto similarity between two binary numpy arrays."""
    a = np.asarray(fp1, dtype=bool)
    b = np.asarray(fp2, dtype=bool)
    intersection = int(np.bitwise_and(a, b).sum())
    union = int(np.bitwise_or(a, b).sum())
    return float(intersection) / float(union) if union > 0 else 0.0


def _extract_synthesis_smiles(synthesis_reaction: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Pull canonical SMILES out of a generated reaction dict (InChI-keyed)."""
    reactant_smiles: List[str] = []
    for r in synthesis_reaction.get("reactants", []):
        if isinstance(r, dict):
            smi = _inchi_to_smiles(r.get("inchi"))
            if smi:
                reactant_smiles.append(smi)

    product_smiles: List[str] = []
    for p in synthesis_reaction.get("products", []):
        if isinstance(p, dict):
            smi = _inchi_to_smiles(p.get("inchi"))
            if smi:
                product_smiles.append(smi)

    return reactant_smiles, product_smiles


def _extract_reference_smiles(reference_reaction: ReferenceReaction) -> Tuple[List[str], List[str]]:
    """Pull canonical, stereo-stripped SMILES out of a ChemOrigins reference reaction."""
    def resolve(mol) -> Optional[str]:
        smi = getattr(mol, "smiles", None)
        if smi:
            return _strip_stereo_smiles(smi)
        return _inchi_to_smiles(getattr(mol, "inchi", None))

    reactant_smiles = [s for s in (resolve(r) for r in reference_reaction.reactants) if s]
    product_smiles = [s for s in (resolve(p) for p in reference_reaction.products) if s]
    return reactant_smiles, product_smiles


def compute_reaction_similarity(
    synthesis_reaction: Dict[str, Any],
    reference_reaction: ReferenceReaction,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> Tuple[float, Dict[str, Any]]:
    """
    DRFP Tanimoto similarity between a synthesis reaction and a reference reaction.

    Args:
        synthesis_reaction: Dict with 'reactants' and 'products' lists of molecule
            dicts (each with an 'inchi' key).
        reference_reaction: ReferenceReaction from ChemOrigins (uses .smiles or
            falls back to .inchi on each Molecule).
        threshold: Retained for API compatibility; not used by DRFP scoring.

    Returns:
        Tuple of:
        - drfp_score: Tanimoto similarity between the two DRFP fingerprints (0.0-1.0)
        - match_details: Dict with the constructed reaction SMILES and any error info
    """
    synth_reactants, synth_products = _extract_synthesis_smiles(synthesis_reaction)
    ref_reactants, ref_products = _extract_reference_smiles(reference_reaction)

    synth_smiles = _build_reaction_smiles(synth_reactants, synth_products)
    ref_smiles = _build_reaction_smiles(ref_reactants, ref_products)

    if not synth_smiles or not ref_smiles:
        return 0.0, {
            "drfp_score": 0.0,
            "synthesis_smiles": synth_smiles,
            "reference_smiles": ref_smiles,
            "error": "Could not build reaction SMILES (missing reactants or products)",
        }

    try:
        fps = DrfpEncoder.encode(
            [synth_smiles, ref_smiles],
            n_folded_length=DRFP_N_BITS,
            radius=DRFP_RADIUS,
        )
        score = _tanimoto(fps[0], fps[1])
    except Exception as e:
        logger.warning(f"DRFP encoding failed for {synth_smiles!r} vs {ref_smiles!r}: {e}")
        return 0.0, {
            "drfp_score": 0.0,
            "synthesis_smiles": synth_smiles,
            "reference_smiles": ref_smiles,
            "error": str(e),
        }

    return score, {
        "drfp_score": score,
        "synthesis_smiles": synth_smiles,
        "reference_smiles": ref_smiles,
    }
