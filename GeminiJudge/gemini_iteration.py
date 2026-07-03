#!/usr/bin/env python3
"""
Gemini 3.1 Pro LLM Judge for iteration-based synthesis networks.

Loads configs A/B/C (iteration 1/2/3) from synth_nets_iterations/gpt5.4_10iter/,
presents them to Gemini in a blind randomized order (relabeled as Config 1,2,3),
and saves the evaluation output as markdown. Runs 5 times per molecule.
"""
import json
import random
import re
import time
from pathlib import Path

from dotenv import load_dotenv
import os
import google.generativeai as genai

# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
SYNTH_NETS_DIR = SCRIPT_DIR / "synth_nets_iterations" / "gpt5.4_10iter"
JUDGE_PROMPT_PATH = SCRIPT_DIR / "judge_prompt.md"
OUTPUT_DIR = SCRIPT_DIR / "llm_judge_iterations" / "gpt5.4_10iter"
CONFIG_ENV = SCRIPT_DIR.parent / "config.env"

# ── Config ─────────────────────────────────────────────────────────────
RUNS_PER_COMBO = 5
MODEL_NAME = "gemini-3.1-pro-preview"
DELAY_BETWEEN_CALLS = 10  # seconds between API calls

TARGET_MOLECULES = [
    # "L-Alanine",
    # "Serine",
    # "Arginine",
    # "Threonine",
    # "Valine",
    "L-Proline",
    "Glycine",
    "Glutamate",
    "Histidine",
]

def molecule_to_filename(molecule: str) -> str:
    """Convert display name to filename stem (e.g. 'L-Alanine' -> 'L_Alanine')."""
    return molecule.replace("-", "_")

def load_configs(molecule: str) -> dict[str, str]:
    """Load available iteration config JSONs for a molecule. Returns {letter: json_text}."""
    file_stem = molecule_to_filename(molecule)
    configs = {}
    # Support up to 26 configs (A-Z) to handle any number of iterations
    for letter in "ABCDEFGHIJ":
        path = SYNTH_NETS_DIR / f"{file_stem}_deep_research_claude_config_{letter}.json"
        if path.exists():
            configs[letter] = path.read_text()
    return configs


def adapt_judge_prompt(base_prompt: str, num_configs: int) -> str:
    """Adapt the judge prompt for the actual number of configs."""
    prompt = base_prompt
    # Replace references to 6 configs
    prompt = prompt.replace("**6 synthesis network variants**", f"**{num_configs} synthesis network variants**")
    prompt = prompt.replace("(Config A through F)", f"(Config 1 through {num_configs})")
    prompt = prompt.replace("all six", f"all {num_configs}")
    prompt = prompt.replace("all six", f"all {num_configs}")
    # Update the ranking table to match config count
    # Remove extra ranking rows (keep only num_configs rows)
    for rank in range(num_configs + 1, 11):
        prompt = prompt.replace(f"| {rank}    |        |             |                   |\n", "")
    return prompt


def build_user_prompt(molecule: str, configs: dict[str, str], order: list[str]) -> str:
    """Build the user message with configs in the given order, relabeled as 1,2,3."""
    parts = [f"# Target Molecule: {molecule}\n"]
    for idx, letter in enumerate(order, 1):
        parts.append(f"## Config {idx}\n\n```json\n{configs[letter]}\n```\n")
    return "\n".join(parts)


def build_mapping_header(order: list[str]) -> str:
    """Build a mapping comment showing true identity of each presented config."""
    lines = ["<!-- Config Mapping (blind evaluation) -->"]
    for idx, letter in enumerate(order, 1):
        lines.append(f"<!-- Config {idx} = Original Config {letter} (iteration {ord(letter) - ord('A') + 1}) -->")
    lines.append("")
    return "\n".join(lines)


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

    # Load and prepare judge prompt
    base_prompt = JUDGE_PROMPT_PATH.read_text()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    print(f"{'='*60}")
    print(f"Model: gpt5.4_10iter (iterations)")
    print(f"{'='*60}")

    for molecule in TARGET_MOLECULES:
        configs = load_configs(molecule)
        if not configs:
            print(f"  {molecule}: no configs found, skipping")
            continue

        letters = sorted(configs.keys())
        num_configs = len(letters)
        system_prompt = adapt_judge_prompt(base_prompt, num_configs)

        print(f"  {molecule}: found {num_configs} configs ({', '.join(letters)})")

        for run_num in range(1, RUNS_PER_COMBO + 1):
            out_path = OUTPUT_DIR / f"{molecule}-Run{run_num}.md"

            # Skip if already exists
            if out_path.exists():
                print(f"    Run{run_num}: already exists, skipping")
                continue

            # Shuffle config order with deterministic seed
            rng = random.Random(run_num)
            order = letters.copy()
            rng.shuffle(order)

            mapping_header = build_mapping_header(order)
            user_prompt = build_user_prompt(molecule, configs, order)

            print(f"    Run{run_num}: order={order}, calling {MODEL_NAME}...", end=" ", flush=True)
            try:
                result = call_gemini(system_prompt, user_prompt)
                out_path.write_text(mapping_header + result)
                print(f"done ({len(result)} chars)")
                total += 1
            except Exception as e:
                print(f"ERROR: {e}")
                print(f"    Retrying in 30s...", end=" ", flush=True)
                time.sleep(30)
                try:
                    result = call_gemini(system_prompt, user_prompt)
                    out_path.write_text(mapping_header + result)
                    print(f"done ({len(result)} chars)")
                    total += 1
                except Exception as e2:
                    print(f"FAILED: {e2}")

            time.sleep(DELAY_BETWEEN_CALLS)

    print(f"\nDone: {total} evaluations written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
