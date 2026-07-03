#!/usr/bin/env python3
"""
Prepare synthesis networks for GeminiJudge evaluation.

For each model folder in results/synthesis_nets_inchi_corrected/,
selects the last attempt file per molecule+config combo,
strips evaluation metadata, adds a config letter (A-F), and saves to
GeminiJudge/synth_nets/{model}/ with clean filenames.
"""
import json
import re
from pathlib import Path
from collections import defaultdict

INPUT_DIR = Path(__file__).parent.parent / "results" / "synthesis_nets_inchi_corrected"
OUTPUT_BASE = Path(__file__).parent / "synth_nets"

REMOVE_KEYS = {"evaluation", "success", "attempts", "notes"}

# Label -> config letter (A-F), ordered by ABLATION_CONFIGS
LABEL_TO_LETTER = {
    "deep_research_claude": "A",
    # "deep_research_gemini": "B",
    # "deep_research_gpt5.4": "C",
    # # "ms_disc": "D",
    # "perfect_rag": "D",
    # "no_research": "E",
    # "Naive": "F",

}

# Pattern: network_{molecule}_{label}_run{N}(_attempt{N}).json
FILE_RE = re.compile(
    r"^network_(.+?)_(.+?)_run\d+(?:_attempt(\d+))?\.json$"
)


def process_model_folder(model_dir: Path, output_dir: Path):
    """Process all network files in a single model folder."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group files by (molecule, label) -> list of (attempt_num, path)
    groups: dict[tuple[str, str], list[tuple[int, Path]]] = defaultdict(list)

    for f in sorted(model_dir.glob("*.json")):
        m = FILE_RE.match(f.name)
        if not m:
            print(f"  Skipping (no match): {f.name}")
            continue
        molecule, label, attempt_str = m.groups()
        attempt_num = int(attempt_str) if attempt_str else 0  # 0 = base file
        groups[(molecule, label)].append((attempt_num, f))

    processed = 0
    for (molecule, label), entries in sorted(groups.items()):
        letter = LABEL_TO_LETTER.get(label)
        if letter is None:
            print(f"  Skipping unknown label: {label}")
            continue

        # Pick highest attempt number (skip base file if attempts exist)
        attempts_only = [(n, p) for n, p in entries if n > 0]
        if attempts_only:
            _, best_file = max(attempts_only, key=lambda x: x[0])
        else:
            # Only base file exists — use it
            _, best_file = entries[0]

        data = json.loads(best_file.read_text())

        # Remove unwanted keys
        for key in REMOVE_KEYS:
            data.pop(key, None)

        # Add config field
        data["config"] = letter

        out_name = f"{molecule}_config_{letter}.json"
        out_path = output_dir / out_name
        out_path.write_text(json.dumps(data, indent=2))

        print(f"  {best_file.name} -> {out_name}")
        processed += 1

    return processed


def main():
    total = 0
    for model_dir in sorted(INPUT_DIR.iterdir()):
        if not model_dir.is_dir():
            continue
        model_name = model_dir.name
        print(f"\n=== Processing model: {model_name} ===")
        output_dir = OUTPUT_BASE / model_name
        count = process_model_folder(model_dir, output_dir)
        print(f"  -> {count} files written to {output_dir}")
        total += count

    print(f"\nDone: {total} total files written to {OUTPUT_BASE}")


if __name__ == "__main__":
    main()
