"""
ChemOrigins reference data loader and parser.

Loads and indexes reference data from ChemOrigins JSON files (e.g., pbmdl-000001.json)
for use by validation agents.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ReferenceMolecule:
    """A molecule from the ChemOrigins reference."""
    key: str
    formula: str
    title: str
    smiles: str
    inchi: str
    inchikey: str
    cid: Optional[str] = None
    iupac_name: Optional[str] = None
    mw: Optional[float] = None


@dataclass
class ReferenceCondition:
    """A condition set from the ChemOrigins reference."""
    key: str
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    ph: Optional[float] = None
    time: Optional[float] = None
    agents: List[Dict[str, Any]] = field(default_factory=list)
    source_file: Optional[str] = None


@dataclass
class ReferenceSource:
    """A literature source from the ChemOrigins reference."""
    title: str
    authors: str
    journal: str
    year: int
    doi: Optional[str] = None


@dataclass
class ReferenceReaction:
    """A reaction from the ChemOrigins reference."""
    key: str
    smiles: str
    reactants: List[ReferenceMolecule]
    products: List[ReferenceMolecule]
    conditions: List[ReferenceCondition]
    sources: List[ReferenceSource]
    img: Optional[str] = None

    def get_reactant_formulas(self) -> List[str]:
        """Get list of reactant formulas."""
        return [r.formula for r in self.reactants]

    def get_product_formulas(self) -> List[str]:
        """Get list of product formulas."""
        return [p.formula for p in self.products]

    def get_reactant_inchikeys(self) -> List[str]:
        """Get list of reactant InChIKeys."""
        return [r.inchikey for r in self.reactants if r.inchikey]

    def get_product_inchikeys(self) -> List[str]:
        """Get list of product InChIKeys."""
        return [p.inchikey for p in self.products if p.inchikey]


@dataclass
class ReferenceModule:
    """A ChemOrigins module (e.g., Alanine-synthesis)."""
    key: str
    name: str
    description: str
    reactions: List[ReferenceReaction]

    def get_reaction_by_key(self, reaction_key: str) -> Optional[ReferenceReaction]:
        """Get a specific reaction by its key."""
        for rxn in self.reactions:
            if rxn.key == reaction_key:
                return rxn
        return None

    def get_all_product_inchikeys(self) -> List[str]:
        """Get all unique product InChIKeys across all reactions."""
        inchikeys = set()
        for rxn in self.reactions:
            for inchikey in rxn.get_product_inchikeys():
                inchikeys.add(inchikey)
        return list(inchikeys)

    def get_all_reactant_inchikeys(self) -> List[str]:
        """Get all unique reactant InChIKeys across all reactions."""
        inchikeys = set()
        for rxn in self.reactions:
            for inchikey in rxn.get_reactant_inchikeys():
                inchikeys.add(inchikey)
        return list(inchikeys)


class ChemOriginsLoader:
    """
    Loader for ChemOrigins reference JSON files.

    Usage:
        loader = ChemOriginsLoader("validator/pbmdl-000001.json")
        module = loader.load()

        # Access reactions
        for reaction in module.reactions:
            print(f"{reaction.key}: {reaction.smiles}")

        # Find reactions by product
        alanine_reactions = loader.find_reactions_by_product_formula("C3H7NO2")
    """

    def __init__(self, reference_path: str):
        """
        Initialize the loader.

        Args:
            reference_path: Path to the ChemOrigins JSON file
        """
        self.reference_path = Path(reference_path)
        self.module: Optional[ReferenceModule] = None
        self._raw_data: Optional[Dict] = None

        # Indexes for fast lookup
        self._reactions_by_key: Dict[str, ReferenceReaction] = {}
        self._reactions_by_product_formula: Dict[str, List[ReferenceReaction]] = {}
        self._reactions_by_product_inchikey: Dict[str, List[ReferenceReaction]] = {}
        self._reactions_by_reactant_formula: Dict[str, List[ReferenceReaction]] = {}
        self._molecules_by_inchikey: Dict[str, ReferenceMolecule] = {}

    def load(self) -> ReferenceModule:
        """
        Load and parse the reference file.

        Returns:
            ReferenceModule: The parsed reference module
        """
        if not self.reference_path.exists():
            raise FileNotFoundError(f"Reference file not found: {self.reference_path}")

        with open(self.reference_path, 'r', encoding='utf-8') as f:
            self._raw_data = json.load(f)

        self.module = self._parse_module(self._raw_data)
        self._build_indexes()

        return self.module

    def _parse_module(self, data: Dict) -> ReferenceModule:
        """Parse the module data."""
        module_info = data.get("module", {})

        reactions = []
        for rxn_data in data.get("reactions", []):
            reaction = self._parse_reaction(rxn_data)
            reactions.append(reaction)

        return ReferenceModule(
            key=module_info.get("key", ""),
            name=module_info.get("name", ""),
            description=module_info.get("description", ""),
            reactions=reactions
        )

    def _parse_reaction(self, rxn_data: Dict) -> ReferenceReaction:
        """Parse a single reaction."""
        # Parse reactants
        reactants = []
        for mol_data in rxn_data.get("reactants", []):
            reactants.append(self._parse_molecule(mol_data))

        # Parse products
        products = []
        for mol_data in rxn_data.get("products", []):
            products.append(self._parse_molecule(mol_data))

        # Parse conditions
        conditions = []
        sources = []
        for cond_data in rxn_data.get("conditions", []):
            condition = self._parse_condition(cond_data.get("condition", {}))
            conditions.append(condition)

            # Also add agents to the condition
            condition.agents = cond_data.get("agents", [])

            # Parse source
            source_data = cond_data.get("sources", {})
            if source_data:
                sources.append(self._parse_source(source_data))

        # Get reaction info
        reaction_info = rxn_data.get("reaction", {})

        return ReferenceReaction(
            key=reaction_info.get("key", ""),
            smiles=reaction_info.get("smiles", ""),
            reactants=reactants,
            products=products,
            conditions=conditions,
            sources=sources,
            img=rxn_data.get("img")
        )

    def _parse_molecule(self, mol_data: Dict) -> ReferenceMolecule:
        """Parse a molecule."""
        return ReferenceMolecule(
            key=mol_data.get("key", ""),
            formula=mol_data.get("formula", ""),
            title=mol_data.get("title", ""),
            smiles=mol_data.get("smiles", ""),
            inchi=mol_data.get("inchi", ""),
            inchikey=mol_data.get("inchikey", ""),
            cid=mol_data.get("cid"),
            iupac_name=mol_data.get("iupac_name"),
            mw=mol_data.get("mw")
        )

    def _parse_condition(self, cond_data: Dict) -> ReferenceCondition:
        """Parse a condition set."""
        return ReferenceCondition(
            key=cond_data.get("key", ""),
            temperature=cond_data.get("temperature"),
            pressure=cond_data.get("pressure"),
            ph=cond_data.get("ph"),
            time=cond_data.get("time"),
            source_file=cond_data.get("source_file")
        )

    def _parse_source(self, source_data: Dict) -> ReferenceSource:
        """Parse a literature source."""
        return ReferenceSource(
            title=source_data.get("title", ""),
            authors=source_data.get("authors", ""),
            journal=source_data.get("journal", ""),
            year=source_data.get("year", 0),
            doi=source_data.get("doi")
        )

    def _build_indexes(self):
        """Build indexes for fast lookup."""
        if not self.module:
            return

        for rxn in self.module.reactions:
            # Index by key
            self._reactions_by_key[rxn.key] = rxn

            # Index by product formula
            for product in rxn.products:
                formula = product.formula
                if formula not in self._reactions_by_product_formula:
                    self._reactions_by_product_formula[formula] = []
                self._reactions_by_product_formula[formula].append(rxn)

                # Index by InChIKey
                if product.inchikey:
                    if product.inchikey not in self._reactions_by_product_inchikey:
                        self._reactions_by_product_inchikey[product.inchikey] = []
                    self._reactions_by_product_inchikey[product.inchikey].append(rxn)

                # Index molecule
                if product.inchikey:
                    self._molecules_by_inchikey[product.inchikey] = product

            # Index by reactant formula
            for reactant in rxn.reactants:
                formula = reactant.formula
                if formula not in self._reactions_by_reactant_formula:
                    self._reactions_by_reactant_formula[formula] = []
                self._reactions_by_reactant_formula[formula].append(rxn)

                # Index molecule
                if reactant.inchikey:
                    self._molecules_by_inchikey[reactant.inchikey] = reactant

    def get_reaction_by_key(self, key: str) -> Optional[ReferenceReaction]:
        """Get a reaction by its key."""
        return self._reactions_by_key.get(key)

    def find_reactions_by_product_formula(self, formula: str) -> List[ReferenceReaction]:
        """Find all reactions that produce a given formula."""
        return self._reactions_by_product_formula.get(formula, [])

    def find_reactions_by_product_inchikey(self, inchikey: str) -> List[ReferenceReaction]:
        """Find all reactions that produce a molecule with given InChIKey."""
        return self._reactions_by_product_inchikey.get(inchikey, [])

    def find_reactions_by_reactant_formula(self, formula: str) -> List[ReferenceReaction]:
        """Find all reactions that use a given formula as reactant."""
        return self._reactions_by_reactant_formula.get(formula, [])

    def get_molecule_by_inchikey(self, inchikey: str) -> Optional[ReferenceMolecule]:
        """Get a molecule by its InChIKey."""
        return self._molecules_by_inchikey.get(inchikey)

    def get_all_reaction_keys(self) -> List[str]:
        """Get all reaction keys in the module."""
        return list(self._reactions_by_key.keys())

    def get_all_product_formulas(self) -> List[str]:
        """Get all unique product formulas."""
        return list(self._reactions_by_product_formula.keys())

    def get_reference_summary(self) -> Dict[str, Any]:
        """Get a summary of the reference data."""
        if not self.module:
            return {}

        return {
            "module_key": self.module.key,
            "module_name": self.module.name,
            "description": self.module.description,
            "num_reactions": len(self.module.reactions),
            "reaction_keys": self.get_all_reaction_keys(),
            "product_formulas": self.get_all_product_formulas(),
            "num_unique_molecules": len(self._molecules_by_inchikey)
        }

    def format_reaction_for_comparison(self, reaction: ReferenceReaction) -> str:
        """
        Format a reference reaction as a human-readable string.

        Args:
            reaction: The reference reaction

        Returns:
            str: Formatted reaction string
        """
        reactant_strs = [f"{r.formula} ({r.title})" for r in reaction.reactants]
        product_strs = [f"{p.formula} ({p.title})" for p in reaction.products]

        return f"{' + '.join(reactant_strs)} -> {' + '.join(product_strs)}"

    def get_conditions_summary(self, reaction: ReferenceReaction) -> Dict[str, Any]:
        """
        Get a summary of conditions for a reaction.

        Args:
            reaction: The reference reaction

        Returns:
            Dict with condition summary
        """
        summary = {
            "temperatures": [],
            "agents": [],
            "sources": []
        }

        for cond in reaction.conditions:
            if cond.temperature is not None:
                summary["temperatures"].append(cond.temperature)
            if cond.agents:
                for agent in cond.agents:
                    summary["agents"].append(agent.get("name", "Unknown"))

        for source in reaction.sources:
            summary["sources"].append({
                "title": source.title,
                "authors": source.authors,
                "year": source.year,
                "doi": source.doi
            })

        return summary
