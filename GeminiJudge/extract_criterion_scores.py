"""Extract per-criterion scores from LLM-judged markdown files.

Parses each Config's scoring table (7 criteria + total) from every
{Molecule}-Run{N}.md file, writes a CSV, and generates summary plots.

Iterates over each model directory in llm_judge/{model}/.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIGS = ["A", "B", "C", "D", "E", "F"]
CONFIG_COLORS = {
    "A": "#4C72B0", "B": "#DD8452", "C": "#55A868",
    "D": "#C44E52", "E": "#8172B3", "F": "#937860",
}
CRITERIA = [
    "Chemical Feasibility",
    "Pathway Coherence",
    "Environmental Consistency",
    "Mechanistic Detail",
    "Network Completeness",
    "Prebiotic Plausibility",
    "Novelty of Reactions",
]

LLM_JUDGE_DIR = Path(__file__).parent / "llm_judge"

# Accumulate per-model mean criterion scores for the combined radar charts
all_model_scores: dict[str, list[float]] = {}
all_model_config_scores: dict[str, dict[str, list[float]]] = {}  # model -> {config -> [means per criterion]}
all_rows: list[list] = []  # accumulate rows across all models for combined CSV

for model_dir in sorted(LLM_JUDGE_DIR.iterdir()):
    if not model_dir.is_dir():
        continue
    model_name = model_dir.name
    print(f"\n{'='*60}\nProcessing model: {model_name}\n{'='*60}")

    INPUT_DIR = model_dir
    OUTPUT_DIR = model_dir
    OUTPUT_CSV = OUTPUT_DIR / f"{model_name}_criterion_scores.csv"

    # -----------------------------------------------------------------------
    # Parsing
    # -----------------------------------------------------------------------
    rows: list[list] = []

    for md_path in sorted(INPUT_DIR.glob("*.md")):
        m = re.match(r"(.+)-Run(\d+)\.md$", md_path.name)
        if not m:
            print(f"WARNING: Skipping {md_path.name}")
            continue
        molecule, run = m.group(1), m.group(2)
        text = md_path.read_text()

        # Split on ### Config X headers
        config_sections = re.split(r"### Config ([A-F])\b", text)
        for idx in range(1, len(config_sections) - 1, 2):
            config_letter = config_sections[idx]
            section_text = config_sections[idx + 1]

            for line in section_text.splitlines():
                line = line.strip()
                if not line.startswith("|"):
                    continue
                if "---" in line:
                    continue
                cols = [c.strip() for c in line.split("|")]
                cols = [c for c in cols if c]
                if len(cols) < 2:
                    continue

                criterion_raw = cols[0].strip("* ")
                score_raw = cols[1].strip("* ")

                for crit in CRITERIA:
                    if crit.lower() in criterion_raw.lower():
                        try:
                            score = int(re.search(r"\d+", score_raw).group())
                        except (AttributeError, ValueError):
                            continue
                        rows.append([molecule, run, config_letter, crit, score])
                        break
                else:
                    if "total" in criterion_raw.lower():
                        total_match = re.search(r"(\d+)", score_raw)
                        if total_match:
                            rows.append([molecule, run, config_letter, "Total", int(total_match.group(1))])

    # -----------------------------------------------------------------------
    # Write CSV
    # -----------------------------------------------------------------------
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Molecule", "Run", "Config", "Criterion", "Score"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")
    all_rows.extend([model_name] + row for row in rows)

    if not rows:
        print("No data found, skipping plots.")
        continue

    # -----------------------------------------------------------------------
    # Build lookup structures
    # -----------------------------------------------------------------------
    global_scores = defaultdict(list)
    mol_scores = defaultdict(list)
    molecules_seen: list[str] = []

    for mol, run, cfg, crit, score in rows:
        global_scores[(cfg, crit)].append(score)
        mol_scores[(mol, cfg, crit)].append(score)
        if mol not in molecules_seen:
            molecules_seen.append(mol)

    molecules = molecules_seen
    ALL_CRITERIA = CRITERIA + ["Total"]

    # Store model-level mean per criterion (across all configs) for combined radar
    model_means = []
    for crit in CRITERIA:
        all_vals = [v for cfg in CONFIGS for v in global_scores[(cfg, crit)]]
        model_means.append(np.mean(all_vals) if all_vals else 0)
    all_model_scores[model_name] = model_means
    # Also store per-config breakdown for side-by-side radar PDF
    all_model_config_scores[model_name] = {}
    for cfg in CONFIGS:
        cfg_means = [np.mean(global_scores[(cfg, crit)]) if global_scores[(cfg, crit)] else 0
                     for crit in CRITERIA]
        all_model_config_scores[model_name][cfg] = cfg_means

    # -----------------------------------------------------------------------
    # Print summary
    # -----------------------------------------------------------------------
    print(f"\n=== [{model_name}] Per-Config Average (across all molecules & runs) ===")
    print(f"{'Config':<10}", end="")
    for crit in ALL_CRITERIA:
        print(f"{crit[:15]:>17}", end="")
    print()
    for cfg in CONFIGS:
        print(f"Config {cfg:<4}", end="")
        for crit in ALL_CRITERIA:
            s = global_scores[(cfg, crit)]
            if s:
                print(f"{np.mean(s):7.1f}±{np.std(s):<7.1f}", end="")
            else:
                print(f"{'N/A':>17}", end="")
        print()

    # -----------------------------------------------------------------------
    # Plot 1: Heatmap — criterion × config
    # -----------------------------------------------------------------------
    heat_data = np.zeros((len(CRITERIA), len(CONFIGS)))
    for i, crit in enumerate(CRITERIA):
        for j, cfg in enumerate(CONFIGS):
            s = global_scores[(cfg, crit)]
            heat_data[i, j] = np.mean(s) if s else 0

    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(heat_data, cmap="RdYlGn", vmin=1, vmax=10, aspect="auto")
    ax.set_xticks(range(len(CONFIGS)))
    ax.set_xticklabels([f"Config {c}" for c in CONFIGS], fontsize=11)
    ax.set_yticks(range(len(CRITERIA)))
    ax.set_yticklabels(CRITERIA, fontsize=10)
    ax.set_title(f"[{model_name}] Mean Criterion Scores by Config\n(averaged across all molecules & runs)",
                 fontsize=13, fontweight="bold")

    for i in range(len(CRITERIA)):
        for j in range(len(CONFIGS)):
            val = heat_data[i, j]
            color = "white" if val < 4 or val > 8 else "black"
            ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                    fontsize=11, fontweight="bold", color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Mean Score (1-10)", fontsize=10)
    fig.tight_layout()
    p = OUTPUT_DIR / f"{model_name}_criterion_heatmap.png"
    fig.savefig(p, dpi=200)
    print(f"\nSaved {p}")
    plt.close(fig)

    # -----------------------------------------------------------------------
    # Plot 2: Radar / spider chart — one trace per config
    # -----------------------------------------------------------------------
    angles = np.linspace(0, 2 * np.pi, len(CRITERIA), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    for cfg in CONFIGS:
        values = [np.mean(global_scores[(cfg, crit)]) if global_scores[(cfg, crit)] else 0
                  for crit in CRITERIA]
        values += values[:1]
        ax.plot(angles, values, "o-", linewidth=2, label=f"Config {cfg}",
                color=CONFIG_COLORS[cfg])
        ax.fill(angles, values, alpha=0.08, color=CONFIG_COLORS[cfg])

    ax.set_thetagrids(np.degrees(angles[:-1]), CRITERIA, fontsize=9)
    ax.set_ylim(0, 10)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_title(f"[{model_name}] Config Criterion Profiles\n(mean across all molecules & runs)",
                 fontsize=13, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)
    fig.tight_layout()
    p = OUTPUT_DIR / f"{model_name}_criterion_radar.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    print(f"Saved {p}")
    plt.close(fig)

    # -----------------------------------------------------------------------
    # Plot 3: Grouped bar chart — mean Total per config per molecule
    # -----------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(14, 6))
    x = np.arange(len(molecules))
    bar_width = 0.13
    n_configs = len(CONFIGS)

    for i, cfg in enumerate(CONFIGS):
        means = [np.mean(mol_scores[(m, cfg, "Total")]) if mol_scores[(m, cfg, "Total")] else 0
                 for m in molecules]
        stds = [np.std(mol_scores[(m, cfg, "Total")]) if mol_scores[(m, cfg, "Total")] else 0
                for m in molecules]
        offset = (i - (n_configs - 1) / 2) * bar_width
        bars = ax.bar(x + offset, means, bar_width, yerr=stds, capsize=3,
                      label=f"Config {cfg}", color=CONFIG_COLORS[cfg],
                      edgecolor="white", linewidth=0.5)
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
    p = OUTPUT_DIR / f"{model_name}_criterion_total_bars.png"
    fig.savefig(p, dpi=200)
    print(f"Saved {p}")
    plt.close(fig)

    # -----------------------------------------------------------------------
    # Plot 4: Summary table — Config × Molecule (Total mean±std)
    # -----------------------------------------------------------------------
    cmap_table = plt.cm.RdYlGn
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.axis("off")

    header = ["Config"] + molecules + ["Overall"]
    table_data = []
    cell_colors = []

    for cfg in CONFIGS:
        row = [f"Config {cfg}"]
        row_colors = ["#f0f0f0"]
        all_totals = []
        for m in molecules:
            s = mol_scores[(m, cfg, "Total")]
            all_totals.extend(s)
            mean_val = np.mean(s) if s else 0
            std_val = np.std(s) if s else 0
            row.append(f"{mean_val:.1f} ± {std_val:.1f}")
            norm = (mean_val - 20) / 50
            row_colors.append(cmap_table(np.clip(norm, 0, 1), alpha=0.35))
        overall_mean = np.mean(all_totals) if all_totals else 0
        overall_std = np.std(all_totals) if all_totals else 0
        row.append(f"{overall_mean:.1f} ± {overall_std:.1f}")
        norm_o = (overall_mean - 20) / 50
        row_colors.append(cmap_table(np.clip(norm_o, 0, 1), alpha=0.5))
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

    ax.set_title(f"[{model_name}] Mean Total Score ± Std Dev (per-criterion extraction)",
                 fontsize=13, fontweight="bold", pad=20)
    fig.tight_layout()
    p = OUTPUT_DIR / f"{model_name}_criterion_score_table.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    print(f"Saved {p}")
    plt.close(fig)

    # -----------------------------------------------------------------------
    # Plot 5: Per-criterion breakdown table (Config × Criterion, overall avg±std)
    # -----------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(14, 4.5))
    ax.axis("off")

    header2 = ["Config"] + CRITERIA + ["Total"]
    table_data2 = []
    cell_colors2 = []

    for cfg in CONFIGS:
        row = [f"Config {cfg}"]
        row_colors = ["#f0f0f0"]
        for crit in ALL_CRITERIA:
            s = global_scores[(cfg, crit)]
            mean_val = np.mean(s) if s else 0
            std_val = np.std(s) if s else 0
            if crit == "Total":
                row.append(f"{mean_val:.1f} ± {std_val:.1f}")
                norm = (mean_val - 20) / 50
            else:
                row.append(f"{mean_val:.1f} ± {std_val:.1f}")
                norm = (mean_val - 1) / 9
            row_colors.append(cmap_table(np.clip(norm, 0, 1), alpha=0.35))
        table_data2.append(row)
        cell_colors2.append(row_colors)

    table2 = ax.table(cellText=table_data2, colLabels=header2, cellColours=cell_colors2,
                      colColours=["#d9d9d9"] * len(header2), loc="center", cellLoc="center")
    table2.auto_set_font_size(False)
    table2.set_fontsize(9)
    table2.scale(1, 1.6)
    for (r, c), cell in table2.get_celld().items():
        cell.set_edgecolor("#cccccc")
        if r == 0:
            cell.set_text_props(fontweight="bold")

    ax.set_title(f"[{model_name}] Per-Criterion Mean ± Std Dev by Config (across all molecules & runs)",
                 fontsize=13, fontweight="bold", pad=20)
    fig.tight_layout()
    p = OUTPUT_DIR / f"{model_name}_criterion_breakdown_table.png"
    fig.savefig(p, dpi=200, bbox_inches="tight")
    print(f"Saved {p}")
    plt.close(fig)

# ---------------------------------------------------------------------------
# Combined radar chart — one trace per model, saved as PDF
# ---------------------------------------------------------------------------
if all_model_scores:
    MODEL_COLORS = [
        "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
        "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
    ]

    angles = np.linspace(0, 2 * np.pi, len(CRITERIA), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    for idx, (model, means) in enumerate(all_model_scores.items()):
        values = means + means[:1]
        color = MODEL_COLORS[idx % len(MODEL_COLORS)]
        ax.plot(angles, values, "o-", linewidth=2, label=model, color=color)
        ax.fill(angles, values, alpha=0.06, color=color)

    ax.set_thetagrids(np.degrees(angles[:-1]), CRITERIA, fontsize=9)
    ax.set_ylim(0, 10)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_title("All Models — Criterion Profiles\n(mean across all configs, molecules & runs)",
                 fontsize=13, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=10)
    fig.tight_layout()
    p = LLM_JUDGE_DIR / "all_models_criterion_radar.pdf"
    fig.savefig(p, bbox_inches="tight")
    print(f"\nSaved combined radar chart: {p}")
    plt.close(fig)

    # -----------------------------------------------------------------------
    # Side-by-side radar charts — one subplot per model, configs as traces
    # -----------------------------------------------------------------------
    n_models = len(all_model_config_scores)
    ncols = 2
    nrows = (n_models + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(11, 5.5 * nrows),
                             subplot_kw=dict(polar=True))
    axes = np.array(axes).flatten().tolist()
    # Hide unused subplots
    for i in range(n_models, len(axes)):
        axes[i].set_visible(False)

    angles = np.linspace(0, 2 * np.pi, len(CRITERIA), endpoint=False).tolist()
    angles += angles[:1]

    for ax, (model, cfg_scores) in zip(axes, all_model_config_scores.items()):
        for cfg in CONFIGS:
            values = cfg_scores[cfg] + cfg_scores[cfg][:1]
            ax.plot(angles, values, "o-", linewidth=1.5, label=f"Config {cfg}",
                    color=CONFIG_COLORS[cfg], markersize=3)
            ax.fill(angles, values, alpha=0.06, color=CONFIG_COLORS[cfg])
        ax.set_thetagrids(np.degrees(angles[:-1]), CRITERIA, fontsize=7)
        ax.set_ylim(0, 10)
        ax.set_yticks([2, 4, 6, 8, 10])
        ax.set_yticklabels(["2", "4", "6", "8", "10"], fontsize=6)
        ax.set_title(model, fontsize=11, fontweight="bold", pad=15)

    # Single shared legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(CONFIGS), fontsize=9,
               bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Per-Model Criterion Profiles by Config\n(mean across all molecules & runs)",
                 fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    p = LLM_JUDGE_DIR / "all_models_criterion_radar_breakdown.pdf"
    fig.savefig(p, bbox_inches="tight")
    print(f"Saved side-by-side radar chart: {p}")
    plt.close(fig)

# ---------------------------------------------------------------------------
# Combined CSV — all models
# ---------------------------------------------------------------------------
if all_rows:
    EIGHT_AA = {
        "L-Alanine", "Serine", "Arginine", "Threonine",
        "Valine", "L-Proline", "Glycine", "Glutamate",
    }
    LETTER_TO_LABEL_8AA = {
        "A": "deep_research_claude",
        "B": "deep_research_gemini",
        "C": "deep_research_gpt5.4",
        "D": "perfect_rag",
        "E": "no_research",
        "F": "Naive",
    }
    LETTER_TO_LABEL_HISTIDINE = {
        "A": "deep_research_claude",
        "B": "deep_research_gemini",
        "C": "deep_research_gpt5.4",
        "D": "no_research",
        "E": "Naive",
    }
    LETTER_TO_LABEL_OTHER = {
        "A": "deep_research_claude",
    }

    def label_for(molecule: str, letter: str) -> str:
        if molecule in EIGHT_AA:
            mapping = LETTER_TO_LABEL_8AA
        elif molecule == "Histidine":
            mapping = LETTER_TO_LABEL_HISTIDINE
        else:
            mapping = LETTER_TO_LABEL_OTHER
        return mapping.get(letter, letter)

    combined_csv = LLM_JUDGE_DIR / "all_models_criterion_scores.csv"
    with open(combined_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Model", "Molecule", "Run", "Config", "Criterion", "Score"])
        for row in all_rows:
            row = list(row)
            row[3] = label_for(row[1], row[3])
            writer.writerow(row)
    print(f"\nWrote {len(all_rows)} rows to {combined_csv}")

print("\nDone!")
