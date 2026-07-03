#!/usr/bin/env python3
"""
Look up InChI values from PubChem for molecules in a network JSON file.
Uses the IUPAC name to query PubChem's PUG REST API.
"""

import json
import sys
import time
import requests
from pathlib import Path


PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


def get_inchi_by_name(name: str) -> str | None:
    """Query PubChem for InChI using compound name."""
    url = f"{PUBCHEM_BASE_URL}/compound/name/{requests.utils.quote(name)}/property/InChI/JSON"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data["PropertyTable"]["Properties"][0]["InChI"]
        elif response.status_code == 404:
            return None
        else:
            print(f"  Warning: HTTP {response.status_code} for '{name}'")
            return None
    except Exception as e:
        print(f"  Error looking up '{name}': {e}")
        return None


def process_network_file(input_path: str, output_path: str | None = None):
    """Process a network JSON file and add InChI values."""
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    with open(input_file) as f:
        data = json.load(f)

    molecules = data.get("network", {}).get("molecules", [])
    if not molecules:
        print("No molecules found in network.")
        return

    print(f"Found {len(molecules)} molecules. Looking up InChI values...\n")

    found = 0
    not_found = []

    for mol in molecules:
        iupac_name = mol.get("iupac_name")
        common_name = mol.get("common_name")
        mol_id = mol.get("id")

        print(f"[{mol_id}] {iupac_name}...", end=" ", flush=True)

        # Try IUPAC name first
        inchi = get_inchi_by_name(iupac_name) if iupac_name else None

        # Fall back to common name if IUPAC fails
        if not inchi and common_name and common_name != iupac_name:
            print(f"trying '{common_name}'...", end=" ", flush=True)
            inchi = get_inchi_by_name(common_name)

        if inchi:
            mol["inchi"] = inchi
            print(f"OK")
            found += 1
        else:
            print("NOT FOUND")
            not_found.append((mol_id, iupac_name, common_name))

        # Rate limiting - be nice to PubChem
        time.sleep(0.2)

    # Save results
    if output_path is None:
        output_path = input_file.with_stem(input_file.stem + "_with_inchi")

    output_file = Path(output_path)
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Results: {found}/{len(molecules)} molecules found")
    print(f"Output saved to: {output_file}")

    if not_found:
        print(f"\nMolecules not found in PubChem:")
        for mol_id, iupac, common in not_found:
            print(f"  {mol_id}: {iupac} ({common})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pubchem_inchi_lookup.py <input.json> [output.json]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    process_network_file(input_file, output_file)
