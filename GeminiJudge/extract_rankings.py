"""Extract Final Ranking tables from LLM-judged markdown files into CSVs and generate plots.

Iterates over each model directory in llm_judge/{model}/.
Also extracts per-criterion scores into a single combined CSV.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

LABEL_TO_LETTER = {
    "deep_research_claude": "A",
    "deep_research_gemini": "B",
    "deep_research_gpt5.4": "C",
    "ms_disc": "D",
    "perfect_rag": "E",
    "no_research": "F",
}
LETTER_TO_LABEL = {v: k for k, v in LABEL_TO_LETTER.items()}
CONFIGS = list(LABEL_TO_LETTER.values())  # ["A","B","C","D","E","F"]
CONFIG_COLORS = {
    "A": "#4C72B0", "B": "#DD8452", "C": "#55A868",
    "D": "#C44E52", "E": "#8172B3", "F": "#937860",
}

LLM_JUDGE_DIR = Path(__file__).parent / "llm_judge"

# Collect per-criterion scores across all models for the combined CSV
all_criterion_rows = []

for model_dir in sorted(LLM_JUDGE_DIR.iterdir()):
    if not model_dir.is_dir():
        continue
    model_name = model_dir.name
    print(f"\n{'='*60}\nProcessing model: {model_name}\n{'='*60}")

    INPUT_DIR = model_dir
    OUTPUT_DIR = model_dir
    OUTPUT_CSV = OUTPUT_DIR / f"{model_name}_rankings.csv"

    rows = []

    for md_path in sorted(INPUT_DIR.glob("*.md")):
        match = re.match(r"(.+)-Run(\d+)\.md$", md_path.name)
        if not match:
            print(f"WARNING: Skipping unrecognized filename: {md_path.name}")
            continue
        molecule, run = match.group(1), match.group(2)

        text = md_path.read_text()

        # --- Extract per-criterion scores from ### Config X sections ---
        for cfg_match in re.finditer(r"### Config ([A-F])\s*\n", text):
            config_letter = cfg_match.group(1)
            config_label = LETTER_TO_LABEL.get(config_letter, config_letter)
            cfg_section = text[cfg_match.end():]
            cfg_section = re.split(r"\n###? ", cfg_section)[0]

            for line in cfg_section.strip().splitlines():
                line = line.strip()
                if not line.startswith("|") or "---" in line or "Criterion" in line:
                    continue
                cols = [c.strip() for c in line.split("|")]
                cols = [c for c in cols if c]
                if len(cols) >= 2:
                    criterion = cols[0].strip("* ")
                    score_str = cols[1].strip("* ")
                    score_match = re.match(r"(\d+)", score_str)
                    if score_match and criterion.lower() != "total":
                        all_criterion_rows.append([
                            model_name, molecule, run, config_label,
                            criterion, int(score_match.group(1))
                        ])

        # --- Extract Final Ranking ---
        section_match = re.search(r"## Final Ranking\s*\n", text)
        if not section_match:
            print(f"WARNING: No '## Final Ranking' section in {md_path.name}")
            continue

        section_text = text[section_match.end():]
        section_text = re.split(r"\n## ", section_text)[0]

        for line in section_text.strip().splitlines():
            line = line.strip()
            if not line.startswith("|") or "---" in line or "Rank" in line:
                continue
            cols = [c.strip() for c in line.split("|")]
            cols = [c for c in cols if c]
            if len(cols) >= 4:
                rank, config, score, differentiator = cols[0], cols[1], cols[2], cols[3]
                config = config.strip("*")
                score = score.strip("*")
                config_label = LETTER_TO_LABEL.get(config, config)
                rows.append([molecule, run, rank, config_label, score, differentiator])

    # Write per-model rankings CSV
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Molecule", "Run", "Rank", "Config", "Total Score", "Key Differentiator"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")

    if not rows:
        print("No data found, skipping plots.")
        continue

    # -----------------------------------------------------------------------
    # Plotting
    # -----------------------------------------------------------------------
    scores = defaultdict(list)
    ranks = defaultdict(list)
    molecules_seen = []

    for mol, run, rank, config_label, score, _diff in rows:
        # Map label back to letter for internal keying
        config = LABEL_TO_LETTER.get(config_label, config_label)
        score_match = re.match(r"(\d+)", score)
        if not score_match:
            continue
        score_num = int(score_match.group(1))
        scores[(mol, config)].append(score_num)
        rank_match = re.match(r"(\d+)", rank)
        if rank_match:
            ranks[(mol, config)].append(int(rank_match.group(1)))
        if mol not in molecules_seen:
            molecules_seen.append(mol)

    molecules = molecules_seen

    # --- Plot 1: Grouped bar chart of mean total score ± std dev ---
    fig, ax = plt.subplots(figsize=(14, 6))
    x = np.arange(len(molecules))
    bar_width = 0.13
    n_configs = len(CONFIGS)

    for i, cfg in enumerate(CONFIGS):
        means = [np.mean(scores[(m, cfg)]) if scores[(m, cfg)] else 0 for m in molecules]
        stds = [np.std(scores[(m, cfg)]) if scores[(m, cfg)] else 0 for m in molecules]
        offset = (i - (n_configs - 1) / 2) * bar_width
        bars = ax.bar(x + offset, means, bar_width, yerr=stds, capsize=3,
                      label=LETTER_TO_LABEL[cfg], color=CONFIG_COLORS[cfg], edgecolor="white", linewidth=0.5)
        for bar, mean in zip(bars, means):
            if mean > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                        f"{mean:.0f}", ha="center", va="bottom", fontsize=7, fontweight="bold")

    ax.set_xlabel("Molecule", fontsize=12)
    ax.set_ylabel("Mean Total Score (across runs)", fontsize=12)
    ax.set_title(f"[{model_name}] Config Performance by Molecule (Mean ± Std Dev)", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(molecules, fontsize=11)
    ax.set_ylim(0, 75)
    ax.legend(title="Config", loc="upper right", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    scores_png = OUTPUT_DIR / f"{model_name}_scores.png"
    fig.savefig(scores_png, dpi=200)
    print(f"Saved score plot to {scores_png}")
    plt.close(fig)

    # --- Plot 2: Heatmap of average rank ---
    rank_matrix = np.array([[np.mean(ranks[(m, cfg)]) if ranks[(m, cfg)] else 0
                             for m in molecules] for cfg in CONFIGS])

    fig, ax = plt.subplots(figsize=(10, 5))
    cmap = plt.cm.RdYlGn_r
    im = ax.imshow(rank_matrix, cmap=cmap, vmin=1, vmax=6, aspect="auto")

    ax.set_xticks(range(len(molecules)))
    ax.set_xticklabels(molecules, fontsize=11)
    ax.set_yticks(range(len(CONFIGS)))
    ax.set_yticklabels([LETTER_TO_LABEL[c] for c in CONFIGS], fontsize=11)
    ax.set_title(f"[{model_name}] Average Rank by Config and Molecule", fontsize=14, fontweight="bold")

    for i in range(len(CONFIGS)):
        for j in range(len(molecules)):
            val = rank_matrix[i, j]
            text_color = "white" if val > 4 or val < 1.5 else "black"
            ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                    fontsize=12, fontweight="bold", color=text_color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Mean Rank (1=best, 6=worst)", fontsize=10)
    fig.tight_layout()
    ranks_png = OUTPUT_DIR / f"{model_name}_ranks_heatmap.png"
    fig.savefig(ranks_png, dpi=200)
    print(f"Saved rank heatmap to {ranks_png}")
    plt.close(fig)

    # --- Plot 3: Summary table of mean ± std scores ---
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.axis("off")

    header = ["Config"] + molecules + ["Overall"]
    table_data = []
    cell_colors = []
    cmap_table = plt.cm.RdYlGn

    for cfg in CONFIGS:
        row = [LETTER_TO_LABEL[cfg]]
        row_colors = ["#f0f0f0"]
        all_scores = []
        for m in molecules:
            s = scores[(m, cfg)]
            all_scores.extend(s)
            mean_val = np.mean(s) if s else 0
            std_val = np.std(s) if s else 0
            row.append(f"{mean_val:.1f} ± {std_val:.1f}")
            norm_val = (mean_val - 20) / 50  # normalize ~20-70 range to 0-1
            row_colors.append(cmap_table(np.clip(norm_val, 0, 1), alpha=0.35))
        overall_mean = np.mean(all_scores) if all_scores else 0
        overall_std = np.std(all_scores) if all_scores else 0
        row.append(f"{overall_mean:.1f} ± {overall_std:.1f}")
        norm_overall = (overall_mean - 20) / 50
        row_colors.append(cmap_table(np.clip(norm_overall, 0, 1), alpha=0.5))
        table_data.append(row)
        cell_colors.append(row_colors)

    table = ax.table(cellText=table_data, colLabels=header, cellColours=cell_colors,
                     colColours=["#d9d9d9"] * len(header), loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.6)

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#cccccc")
        if r == 0:
            cell.set_text_props(fontweight="bold")

    ax.set_title(f"[{model_name}] Mean Total Score ± Std Dev (across runs)", fontsize=13,
                 fontweight="bold", pad=20)
    fig.tight_layout()
    table_png = OUTPUT_DIR / f"{model_name}_score_table.png"
    fig.savefig(table_png, dpi=200, bbox_inches="tight")
    print(f"Saved score table to {table_png}")
    plt.close(fig)

# -----------------------------------------------------------------------
# Write combined per-criterion scores CSV
# -----------------------------------------------------------------------
ALL_SCORES_CSV = LLM_JUDGE_DIR / "all_scores.csv"
with open(ALL_SCORES_CSV, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Model", "Molecule", "Run", "Config", "Criterion", "Score"])
    writer.writerows(all_criterion_rows)
print(f"\nWrote {len(all_criterion_rows)} criterion scores to {ALL_SCORES_CSV}")

print("\nDone!")
