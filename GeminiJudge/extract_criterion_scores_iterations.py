"""Extract per-criterion scores from iteration-based LLM-judged markdown files.

Parses each Config's scoring table (7 criteria + total) from every
{Molecule}-Run{N}.md file in llm_judge_iterations/gpt5.4_10iter/.
Maps blind Config 1/2/3 back to Iteration 1/2/3 using the HTML comment
mapping at the top of each file.

Writes a CSV and generates summary plots with Iteration labels.
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
ITERATIONS = [str(i) for i in range(1, 11)]
ITER_COLORS = {
    "1": "#4C72B0", "2": "#DD8452", "3": "#55A868",
    "4": "#C44E52", "5": "#8172B3", "6": "#937860",
    "7": "#DA8BC3", "8": "#8C8C8C", "9": "#CCB974",
    "10": "#64B5CD",
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
ALL_CRITERIA = CRITERIA + ["Total"]

MODEL_NAME = "gpt5.4_10iter"
INPUT_DIR = Path(__file__).parent / "llm_judge_iterations" / MODEL_NAME
OUTPUT_DIR = INPUT_DIR
OUTPUT_CSV = OUTPUT_DIR / f"{MODEL_NAME}_criterion_scores.csv"

# Regex for mapping comment: <!-- Config 1 = Original Config C (iteration 3) -->
MAPPING_RE = re.compile(
    r"<!--\s*Config\s+(\d+)\s*=\s*Original Config\s+[A-Z]\s+\(iteration\s+(\d+)\)\s*-->"
)

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
rows: list[list] = []

for md_path in sorted(INPUT_DIR.glob("*.md")):
    m = re.match(r"(.+)-Run(\d+)\.md$", md_path.name)
    if not m:
        print(f"WARNING: Skipping {md_path.name}")
        continue
    molecule, run = m.group(1), m.group(2)
    text = md_path.read_text()

    # Parse blind → iteration mapping from HTML comments
    blind_to_iter = {}
    for mm in MAPPING_RE.finditer(text):
        blind_num, iter_num = mm.group(1), mm.group(2)
        blind_to_iter[blind_num] = iter_num

    if not blind_to_iter:
        print(f"WARNING: No mapping found in {md_path.name}, skipping")
        continue

    # Split on ### Config N headers (numeric)
    config_sections = re.split(r"### Config (\d+)\b", text)
    for idx in range(1, len(config_sections) - 1, 2):
        blind_config = config_sections[idx]
        section_text = config_sections[idx + 1]

        iteration = blind_to_iter.get(blind_config)
        if iteration is None:
            print(f"WARNING: No mapping for Config {blind_config} in {md_path.name}")
            continue

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
                    rows.append([molecule, run, iteration, crit, score])
                    break
            else:
                if "total" in criterion_raw.lower():
                    total_match = re.search(r"(\d+)", score_raw)
                    if total_match:
                        rows.append([molecule, run, iteration, "Total", int(total_match.group(1))])

# ---------------------------------------------------------------------------
# Write CSV
# ---------------------------------------------------------------------------
with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Molecule", "Run", "Iteration", "Criterion", "Score"])
    writer.writerows(rows)
print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")

if not rows:
    print("No data found, skipping plots.")
    exit()

# ---------------------------------------------------------------------------
# Build lookup structures
# ---------------------------------------------------------------------------
global_scores = defaultdict(list)
mol_scores = defaultdict(list)
molecules_seen: list[str] = []

for mol, run, iteration, crit, score in rows:
    global_scores[(iteration, crit)].append(score)
    mol_scores[(mol, iteration, crit)].append(score)
    if mol not in molecules_seen:
        molecules_seen.append(mol)

molecules = molecules_seen

# Determine which iterations actually have data
active_iters = sorted({it for it, _ in global_scores.keys()}, key=int)

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print(f"\n=== [{MODEL_NAME}] Per-Iteration Average (across all molecules & runs) ===")
print(f"{'Iteration':<14}", end="")
for crit in ALL_CRITERIA:
    print(f"{crit[:15]:>17}", end="")
print()
for it in active_iters:
    print(f"Iteration {it:<4}", end="")
    for crit in ALL_CRITERIA:
        s = global_scores[(it, crit)]
        if s:
            print(f"{np.mean(s):7.1f}±{np.std(s):<7.1f}", end="")
        else:
            print(f"{'N/A':>17}", end="")
    print()

# ---------------------------------------------------------------------------
# Plot 1: Heatmap — criterion × iteration
# ---------------------------------------------------------------------------
heat_data = np.zeros((len(CRITERIA), len(active_iters)))
for i, crit in enumerate(CRITERIA):
    for j, it in enumerate(active_iters):
        s = global_scores[(it, crit)]
        heat_data[i, j] = np.mean(s) if s else 0

fig, ax = plt.subplots(figsize=(7, 6))
im = ax.imshow(heat_data, cmap="RdYlGn", vmin=1, vmax=10, aspect="auto")
ax.set_xticks(range(len(active_iters)))
ax.set_xticklabels([f"Iteration {it}" for it in active_iters], fontsize=11)
ax.set_yticks(range(len(CRITERIA)))
ax.set_yticklabels(CRITERIA, fontsize=10)
ax.set_title(f"[{MODEL_NAME}] Mean Criterion Scores by Iteration\n(averaged across all molecules & runs)",
             fontsize=13, fontweight="bold")

for i in range(len(CRITERIA)):
    for j in range(len(active_iters)):
        val = heat_data[i, j]
        color = "white" if val < 4 or val > 8 else "black"
        ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                fontsize=11, fontweight="bold", color=color)

cbar = fig.colorbar(im, ax=ax, shrink=0.8)
cbar.set_label("Mean Score (1-10)", fontsize=10)
fig.tight_layout()
p = OUTPUT_DIR / f"{MODEL_NAME}_criterion_heatmap.pdf"
fig.savefig(p, dpi=200)
print(f"\nSaved {p}")
plt.close(fig)

# ---------------------------------------------------------------------------
# Plot 2: Radar / spider chart — one trace per iteration
# ---------------------------------------------------------------------------
angles = np.linspace(0, 2 * np.pi, len(CRITERIA), endpoint=False).tolist()
angles += angles[:1]

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
for it in active_iters:
    values = [np.mean(global_scores[(it, crit)]) if global_scores[(it, crit)] else 0
              for crit in CRITERIA]
    values += values[:1]
    ax.plot(angles, values, "o-", linewidth=2, label=f"Iteration {it}",
            color=ITER_COLORS.get(it, "#333333"))
    ax.fill(angles, values, alpha=0.08, color=ITER_COLORS.get(it, "#333333"))

ax.set_thetagrids(np.degrees(angles[:-1]), CRITERIA, fontsize=9)
ax.set_ylim(0, 10)
ax.set_yticks([2, 4, 6, 8, 10])
ax.set_title(f"[{MODEL_NAME}] Iteration Criterion Profiles\n(mean across all molecules & runs)",
             fontsize=13, fontweight="bold", pad=20)
ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)
fig.tight_layout()
p = OUTPUT_DIR / f"{MODEL_NAME}_criterion_radar.pdf"
fig.savefig(p, dpi=200, bbox_inches="tight")
print(f"Saved {p}")
plt.close(fig)

# ---------------------------------------------------------------------------
# Plot 3: Grouped bar chart — mean Total per iteration per molecule
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(20, 7))
x = np.arange(len(molecules))
n_iters = len(active_iters)
bar_width = 0.8 / max(n_iters, 1)

for i, it in enumerate(active_iters):
    means = [np.mean(mol_scores[(m, it, "Total")]) if mol_scores[(m, it, "Total")] else 0
             for m in molecules]
    stds = [np.std(mol_scores[(m, it, "Total")]) if mol_scores[(m, it, "Total")] else 0
            for m in molecules]
    offset = (i - (n_iters - 1) / 2) * bar_width
    bars = ax.bar(x + offset, means, bar_width, yerr=stds, capsize=3,
                  label=f"Iteration {it}", color=ITER_COLORS.get(it, "#333333"),
                  edgecolor="white", linewidth=0.5)
    for bar, mean in zip(bars, means):
        if mean > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                    f"{mean:.0f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

ax.set_xlabel("Molecule", fontsize=12)
ax.set_ylabel("Mean Total Score (across runs)", fontsize=12)
ax.set_title(f"[{MODEL_NAME}] Iteration Performance by Molecule (Mean ± Std Dev)", fontsize=14, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(molecules, fontsize=11)
ax.set_ylim(0, 75)
ax.legend(title="Iteration", loc="upper right", fontsize=10)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
p = OUTPUT_DIR / f"{MODEL_NAME}_criterion_total_bars.pdf"
fig.savefig(p, dpi=200)
print(f"Saved {p}")
plt.close(fig)

# ---------------------------------------------------------------------------
# Plot 4: Summary table — Iteration × Molecule (Total mean±std)
# ---------------------------------------------------------------------------
cmap_table = plt.cm.RdYlGn
fig, ax = plt.subplots(figsize=(16, max(4, 1 + len(active_iters) * 0.5)))
ax.axis("off")

header = ["Iteration"] + molecules + ["Overall"]
table_data = []
cell_colors = []

for it in active_iters:
    row = [f"Iteration {it}"]
    row_colors = ["#f0f0f0"]
    all_totals = []
    for m in molecules:
        s = mol_scores[(m, it, "Total")]
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

ax.set_title(f"[{MODEL_NAME}] Mean Total Score ± Std Dev by Iteration",
             fontsize=13, fontweight="bold", pad=20)
fig.tight_layout()
p = OUTPUT_DIR / f"{MODEL_NAME}_criterion_score_table.pdf"
fig.savefig(p, dpi=200, bbox_inches="tight")
print(f"Saved {p}")
plt.close(fig)

# ---------------------------------------------------------------------------
# Plot 5: Per-criterion breakdown table (Iteration × Criterion, overall avg±std)
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(18, max(4, 1 + len(active_iters) * 0.5)))
ax.axis("off")

header2 = ["Iteration"] + CRITERIA + ["Total"]
table_data2 = []
cell_colors2 = []

for it in active_iters:
    row = [f"Iteration {it}"]
    row_colors = ["#f0f0f0"]
    for crit in ALL_CRITERIA:
        s = global_scores[(it, crit)]
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

ax.set_title(f"[{MODEL_NAME}] Per-Criterion Mean ± Std Dev by Iteration (across all molecules & runs)",
             fontsize=13, fontweight="bold", pad=20)
fig.tight_layout()
p = OUTPUT_DIR / f"{MODEL_NAME}_criterion_breakdown_table.pdf"
fig.savefig(p, dpi=200, bbox_inches="tight")
print(f"Saved {p}")
plt.close(fig)

# ---------------------------------------------------------------------------
# LaTeX tables → tables.tex
# ---------------------------------------------------------------------------

def fmt_cell(mean_val, std_val, is_best=False, is_worst=False):
    """Format a cell with optional green/red highlighting."""
    if np.isnan(std_val):
        std_val = 0.0
    inner = f"${mean_val:.2f} \\pm {std_val:.2f}$"
    if is_best:
        return f"\\cellcolor{{green!20}}{inner}"
    elif is_worst:
        return f"\\cellcolor{{red!20}}{inner}"
    return inner


def escape_latex(s):
    return s.replace("_", "\\_").replace("&", "\\&").replace("%", "\\%")


short_criteria = [c.replace("Chemical Feasibility", "Chem. Feas.")
                   .replace("Pathway Coherence", "Path. Coh.")
                   .replace("Environmental Consistency", "Env. Cons.")
                   .replace("Mechanistic Detail", "Mech. Det.")
                   .replace("Network Completeness", "Net. Comp.")
                   .replace("Prebiotic Plausibility", "Preb. Plaus.")
                   .replace("Novelty of Reactions", "Novelty")
                  for c in CRITERIA]

latex_lines = []

# ── Table 1: Criterion scores by iteration ──
latex_lines.append("% =============================================================")
latex_lines.append(f"% Table 1: Criterion Scores by Iteration [{MODEL_NAME}]")
latex_lines.append("% =============================================================")
latex_lines.append("\\begin{table}[ht]")
latex_lines.append("\\centering")
latex_lines.append(f"\\caption{{Mean criterion scores by iteration for {escape_latex(MODEL_NAME)}, averaged across all molecules and runs.}}")
latex_lines.append(f"\\label{{tab:iter_criterion_{MODEL_NAME}}}")
latex_lines.append("\\begin{tabular}{l" + "c" * len(CRITERIA) + "c}")
latex_lines.append("\\toprule")
latex_lines.append("Iteration & " + " & ".join(short_criteria) + " & Total \\\\")
latex_lines.append("\\midrule")

for it in active_iters:
    vals = []
    for crit in CRITERIA:
        s = global_scores[(it, crit)]
        vals.append(f"{np.mean(s):.2f}" if s else "---")
    s_total = global_scores[(it, "Total")]
    vals.append(f"{np.mean(s_total):.2f}" if s_total else "---")
    latex_lines.append(f"Iteration {it} & " + " & ".join(vals) + " \\\\")

latex_lines.append("\\bottomrule")
latex_lines.append("\\end{tabular}")
latex_lines.append("\\end{table}")
latex_lines.append("")

# ── Table 2: Per-iteration overall summary (mean ± std) ──
latex_lines.append("% =============================================================")
latex_lines.append(f"% Table 2: Per-Iteration Overall Summary [{MODEL_NAME}]")
latex_lines.append("% =============================================================")
latex_lines.append("\\begin{table}[ht]")
latex_lines.append("\\centering")
latex_lines.append(f"\\caption{{Overall Gemini Judge total scores per iteration for {escape_latex(MODEL_NAME)}, averaged across all molecules and runs. Best and worst highlighted.}}")
latex_lines.append(f"\\label{{tab:iter_overall_{MODEL_NAME}}}")
latex_lines.append("\\begin{tabular}{lc}")
latex_lines.append("\\toprule")
latex_lines.append("Iteration & Total Score \\\\")
latex_lines.append("\\midrule")

iter_overall = {}
for it in active_iters:
    s = global_scores[(it, "Total")]
    iter_overall[it] = (np.mean(s) if s else 0, np.std(s) if s else 0)

best_it = max(iter_overall, key=lambda k: iter_overall[k][0])
worst_it = min(iter_overall, key=lambda k: iter_overall[k][0])

for it in active_iters:
    m, s = iter_overall[it]
    cell = fmt_cell(m, s, it == best_it, it == worst_it)
    latex_lines.append(f"Iteration {it} & {cell} \\\\")

latex_lines.append("\\bottomrule")
latex_lines.append("\\end{tabular}")
latex_lines.append("\\end{table}")
latex_lines.append("")

# ── Table 3: Iteration × Molecule total scores ──
latex_lines.append("% =============================================================")
latex_lines.append(f"% Table 3: Iteration x Molecule Total Scores [{MODEL_NAME}]")
latex_lines.append("% =============================================================")
latex_lines.append("\\begin{table}[ht]")
latex_lines.append("\\centering")
latex_lines.append(f"\\caption{{Mean total scores ($\\pm$ std) per iteration and molecule for {escape_latex(MODEL_NAME)}. Per-molecule best in green, worst in red.}}")
latex_lines.append(f"\\label{{tab:iter_molecule_{MODEL_NAME}}}")
latex_lines.append("\\begin{tabular}{l" + "c" * len(molecules) + "c}")
latex_lines.append("\\toprule")
mol_headers = [escape_latex(m) for m in molecules]
latex_lines.append("Iteration & " + " & ".join(mol_headers) + " & Overall \\\\")
latex_lines.append("\\midrule")

for it in active_iters:
    cells = []
    all_totals = []
    for m in molecules:
        s = mol_scores[(m, it, "Total")]
        all_totals.extend(s)
        mean_val = np.mean(s) if s else 0
        std_val = np.std(s) if s else 0
        cells.append(f"${mean_val:.1f} \\pm {std_val:.1f}$")
    overall_m = np.mean(all_totals) if all_totals else 0
    overall_s = np.std(all_totals) if all_totals else 0
    cells.append(f"${overall_m:.1f} \\pm {overall_s:.1f}$")
    latex_lines.append(f"Iteration {it} & " + " & ".join(cells) + " \\\\")

latex_lines.append("\\bottomrule")
latex_lines.append("\\end{tabular}")
latex_lines.append("\\end{table}")
latex_lines.append("")

# ── Table 4: Per-criterion breakdown with mean ± std ──
latex_lines.append("% =============================================================")
latex_lines.append(f"% Table 4: Per-Criterion Mean ± Std by Iteration [{MODEL_NAME}]")
latex_lines.append("% =============================================================")
latex_lines.append("\\begin{table}[ht]")
latex_lines.append("\\centering")
latex_lines.append(f"\\caption{{Per-criterion mean $\\pm$ std by iteration for {escape_latex(MODEL_NAME)}, across all molecules and runs.}}")
latex_lines.append(f"\\label{{tab:iter_criterion_detail_{MODEL_NAME}}}")
latex_lines.append("\\begin{tabular}{l" + "c" * len(CRITERIA) + "c}")
latex_lines.append("\\toprule")
latex_lines.append("Iteration & " + " & ".join(short_criteria) + " & Total \\\\")
latex_lines.append("\\midrule")

for it in active_iters:
    cells = []
    for crit in ALL_CRITERIA:
        s = global_scores[(it, crit)]
        mean_val = np.mean(s) if s else 0
        std_val = np.std(s) if s else 0
        cells.append(f"${mean_val:.1f} \\pm {std_val:.1f}$")
    latex_lines.append(f"Iteration {it} & " + " & ".join(cells) + " \\\\")

latex_lines.append("\\bottomrule")
latex_lines.append("\\end{tabular}")
latex_lines.append("\\end{table}")
latex_lines.append("")

# ── Table 5: Per-molecule criterion breakdown (one table per molecule) ──
latex_lines.append("% =============================================================")
latex_lines.append(f"% Tables 5+: Per-Molecule Criterion Breakdown [{MODEL_NAME}]")
latex_lines.append("% =============================================================")

for mol in molecules:
    safe_mol = mol.replace(" ", "_").replace("-", "_").replace(".", "")
    latex_lines.append("\\begin{table}[ht]")
    latex_lines.append("\\centering")
    latex_lines.append(f"\\caption{{Per-criterion mean scores by iteration for {escape_latex(mol)} ({escape_latex(MODEL_NAME)}).}}")
    latex_lines.append(f"\\label{{tab:iter_{safe_mol}_{MODEL_NAME}}}")
    latex_lines.append("\\begin{tabular}{l" + "c" * len(CRITERIA) + "c}")
    latex_lines.append("\\toprule")
    latex_lines.append("Iteration & " + " & ".join(short_criteria) + " & Total \\\\")
    latex_lines.append("\\midrule")

    for it in active_iters:
        vals = []
        for crit in CRITERIA:
            s = mol_scores[(mol, it, crit)]
            vals.append(f"{np.mean(s):.2f}" if s else "---")
        s_total = mol_scores[(mol, it, "Total")]
        vals.append(f"{np.mean(s_total):.2f}" if s_total else "---")
        latex_lines.append(f"Iteration {it} & " + " & ".join(vals) + " \\\\")

    latex_lines.append("\\bottomrule")
    latex_lines.append("\\end{tabular}")
    latex_lines.append("\\end{table}")
    latex_lines.append("")

# ── Write to file ──
tables_path = OUTPUT_DIR / "tables.tex"
tables_path.write_text("\n".join(latex_lines))
print(f"\nSaved LaTeX tables: {tables_path}")

print("\nDone!")
