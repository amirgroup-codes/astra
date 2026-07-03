#!/usr/bin/env python3
"""
Gemini 3.1 Pro LLM Judge for prebiotic synthesis networks.

For each model directory in synth_nets/, sends configs A-F with the judge
prompt to Gemini 3.1 Pro and saves the evaluation output as markdown.
Runs five times per molecule/model combination.
"""
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import os

import google.generativeai as genai

# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
SYNTH_NETS_DIR = SCRIPT_DIR / "synth_nets"
JUDGE_PROMPT_PATH = SCRIPT_DIR / "judge_prompt.md"
OUTPUT_BASE = SCRIPT_DIR / "llm_judge"
CONFIG_ENV = SCRIPT_DIR.parent / "config.env"

# ── Config ─────────────────────────────────────────────────────────────
CONFIG_LETTERS = ["A"]
RUNS_PER_COMBO = 5
MODEL_NAME = "gemini-3.1-pro-preview"
DELAY_BETWEEN_CALLS = 10  # seconds between API calls

TARGET_MOLECULES = [
    "Asparagine",
    "Aspartic Acid",
    "Cysteine",
    "Glutamine",
    "Isoleucine",
    "Leucine",
    "Lysine",
    "Methionine",
    "Phenylalanine",
    "Tryptophan",
    "Tyrosine",
]


def molecule_to_filename(molecule: str) -> str:
    """Convert display name to filename stem (e.g. 'L-Alanine' -> 'L_Alanine', 'Aspartic Acid' -> 'Aspartic_Acid')."""
    return molecule.replace("-", "_").replace(" ", "_")


def load_configs(model_dir: Path, molecule: str) -> dict[str, str]:
    """Load available config JSONs for a molecule. Returns {letter: json_text}."""
    file_stem = molecule_to_filename(molecule)
    configs = {}
    for letter in CONFIG_LETTERS:
        path = model_dir / f"{file_stem}_config_{letter}.json"
        if path.exists():
            configs[letter] = path.read_text()
    return configs


def build_user_prompt(molecule: str, configs: dict[str, str]) -> str:
    """Build the user message with all config JSONs."""
    parts = [f"# Target Molecule: {molecule}\n"]
    for letter in CONFIG_LETTERS:
        if letter in configs:
            parts.append(f"## Config {letter}\n\n```json\n{configs[letter]}\n```\n")
    return "\n".join(parts)


def call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Call Gemini 3.1 Pro and return the response text."""
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system_prompt,
    )
    response = model.generate_content(
        user_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=1.0,
            max_output_tokens=65536,
        ),
    )
    return response.text


def main():
    # Load API key
    load_dotenv(CONFIG_ENV)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not found in config.env")
    genai.configure(api_key=api_key)

    # Load judge prompt
    system_prompt = JUDGE_PROMPT_PATH.read_text()

    # Discover model directories
    model_dirs = sorted(
        d for d in SYNTH_NETS_DIR.iterdir() if d.is_dir()
    )
    if not model_dirs:
        print("No model directories found in synth_nets/")
        return

    total = 0
    for model_dir in model_dirs:
        model_name = model_dir.name
        print(f"\n{'='*60}")
        print(f"Model: {model_name}")
        print(f"{'='*60}")

        output_dir = OUTPUT_BASE / model_name
        output_dir.mkdir(parents=True, exist_ok=True)

        for molecule in TARGET_MOLECULES:
            configs = load_configs(model_dir, molecule)
            if not configs:
                print(f"  {molecule}: no configs found, skipping")
                continue

            print(f"  {molecule}: found configs {', '.join(sorted(configs.keys()))}")
            user_prompt = build_user_prompt(molecule, configs)

            for run_num in range(1, RUNS_PER_COMBO + 1):
                out_path = output_dir / f"{molecule}-Run{run_num}.md"

                # Skip if already exists
                if out_path.exists():
                    print(f"    Run{run_num}: already exists, skipping")
                    continue

                print(f"    Run{run_num}: calling {MODEL_NAME}...", end=" ", flush=True)
                try:
                    result = call_gemini(system_prompt, user_prompt)
                    out_path.write_text(result)
                    print(f"done ({len(result)} chars)")
                    total += 1
                except Exception as e:
                    print(f"ERROR: {e}")
                    # Retry once after longer delay
                    print(f"    Retrying in 30s...", end=" ", flush=True)
                    time.sleep(30)
                    try:
                        result = call_gemini(system_prompt, user_prompt)
                        out_path.write_text(result)
                        print(f"done ({len(result)} chars)")
                        total += 1
                    except Exception as e2:
                        print(f"FAILED: {e2}")

                time.sleep(DELAY_BETWEEN_CALLS)

    print(f"\nDone: {total} evaluations written to {OUTPUT_BASE}")


if __name__ == "__main__":
    main()
