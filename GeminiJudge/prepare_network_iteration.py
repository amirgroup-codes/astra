#!/usr/bin/env python3
"""
Prepare synthesis networks by iteration for GeminiJudge evaluation.

For each model folder in results/synthesis_nets_inchi_corrected/,
maps attempt numbers to config letters (attempt1→A, attempt2→B, attempt3→C),
strips evaluation metadata, and saves to
GeminiJudge/synth_nets_iterations/{model}/ with clean filenames.

Excludes "Final" files (base files without _attempt suffix).
"""
import json
import re
from pathlib import Path

INPUT_DIR = Path(__file__).parent.parent / "results" / "synthesis_nets_inchi_corrected"
OUTPUT_BASE = Path(__file__).parent / "synth_nets_iterations"

REMOVE_KEYS = {"evaluation", "success", "attempts", "notes"}

# Only process these
MODEL_FILTER = {"gpt5.4_10iter"}
LABEL_FILTER = {"deep_research_claude"}

# Attempt number -> config letter
ATTEMPT_TO_LETTER = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F", 7: "G", 8: "H", 9: "I", 10: "J"}

# Pattern: network_{molecule}_{timestamp}_{label}_run{N}_attempt{N}.json
FILE_RE = re.compile(
    r"^network_(.+?)_\d{8}_\d{6}_(.+?)_run\d+_attempt(\d+)\.json$"
)


def process_model_folder(model_dir: Path, output_dir: Path):
    """Process all network attempt files in a single model folder."""
    output_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    for f in sorted(model_dir.glob("*.json")):
        m = FILE_RE.match(f.name)
        if not m:
            continue  # Skip base/Final files and non-matching files

        molecule, label, attempt_str = m.groups()
        if label not in LABEL_FILTER:
            continue
        attempt_num = int(attempt_str)

        letter = ATTEMPT_TO_LETTER.get(attempt_num)
        if letter is None:
            print(f"  Skipping unknown attempt number: {attempt_num} in {f.name}")
            continue

        data = json.loads(f.read_text())

        # Remove unwanted keys
        for key in REMOVE_KEYS:
            data.pop(key, None)

        # Add config field
        data["config"] = letter

        out_name = f"{molecule}_{label}_config_{letter}.json"
        out_path = output_dir / out_name
        out_path.write_text(json.dumps(data, indent=2))

        print(f"  {f.name} -> {out_name}")
        processed += 1

    return processed


def main():
    total = 0
    for model_dir in sorted(INPUT_DIR.iterdir()):
        if not model_dir.is_dir():
            continue
        model_name = model_dir.name
        if model_name not in MODEL_FILTER:
            continue
        print(f"\n=== Processing model: {model_name} ===")
        output_dir = OUTPUT_BASE / model_name
        count = process_model_folder(model_dir, output_dir)
        print(f"  -> {count} files written to {output_dir}")
        total += count

    print(f"\nDone: {total} total files written to {OUTPUT_BASE}")


if __name__ == "__main__":
    main()
