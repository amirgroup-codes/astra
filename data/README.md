# `data/` — Archived experiment results & figure data

This directory holds the **curated outputs of the ablation study** and the
**CSV tables that back the paper figures**. It is the paper-ready snapshot of
what the pipeline produces (`pipeline.py generate → inchi → validate`), grouped
per LLM backend so results can be compared across models.

Nothing here is generated at runtime by the pipeline directly — these are the
frozen, InChI-corrected networks, their validation reports, the run logs, and
the aggregated metrics used to plot the figures.

## Study design

Every result is indexed by three axes:

| Axis | Values |
|---|---|
| **Model** (LLM backend) | `claude_opus4.6`, `gpt41`, `gpt5.4` |
| **Config** (research/context source) | `no_research`, `perfect_rag`, `ms_disc`, `deep_research_claude`, `deep_research_gemini`, `deep_research_gpt5.4`, `Naive` |
| **Target molecule** | 33 targets — amino acids, nucleobases, and central metabolites (e.g. `Glycine`, `Arginine`, `L_Alanine`, `Adenine`, `Uracil`, `Glucose`, `Ribose`, `ATP`, `Acetyl_CoA`, `Pyruvate`, `Oxaloacetate`, `Decanoic_Acid`, …) |

Each `(model, config, molecule)` cell is one `run1`, with up to 3 critic-driven
retry **attempts** saved alongside the final accepted result.

## Layout

| Path | Contents |
|---|---|
| `synthesis_nets_inchi_corrected/{model}/` | Generated synthesis networks (JSON), after the InChI-backfill stage |
| `validation_reports/{model}/` | Per-network validation vs. ChemOrigins reference (JSON), plus `attempt_scores.png` and `ablation_results.tex` |
| `validation_reports/scores.csv` | **Aggregated metrics** across every model/config/molecule/iteration — the master results table |
| `logs/logs_{model}/` | Per-run workflow logs (`*.log`) and JSONL I/O logs (`io/`) capturing every LLM call |
| `figs_data/` | CSV tables backing the paper figures (Fig 2a–2d, Fig 3) |

`{model}` ∈ `{claude_opus4.6, gpt41, gpt5.4}`. The `logs/` folder also contains
supplemental GPT-5.4 batches (`logs_gpt5.4_rest_AA`, `logs_rest_of_AA_gpt5.4`)
covering additional amino-acid targets run separately.

## File naming convention

```
network_{Molecule}_{config}_run{n}[_attempt{m}].json
```

- No `_attempt` suffix → the **final accepted** network for that run.
- `_attempt{m}` → intermediate retry `m` (rejected/refined by the CriticAgent).

Validation reports mirror this with a `_validation` suffix:

```
network_{Molecule}_{config}_run{n}[_attempt{m}]_validation.json
```

## File schemas

**Synthesis network** (`synthesis_nets_inchi_corrected/…json`) — a
`NetworkSynthesisResult`:
- `target_molecule`, `success`, `attempts`, `notes`, `evaluation` (critic score)
- `network`: `{ target_molecule, overall_strategy, molecules[], reactions[],
  pathways[], hub_molecules[], convergence_points[] }`

**Validation report** (`validation_reports/…_validation.json`):
- `overall_precision_score`, `overall_recall_score`, `validator_scores`
- `molecule_match` — coverage vs. reference molecules, with per-molecule matches
  by common name / IUPAC / InChI
- `reaction_validations`, `reaction_recall`, `total_reference_reactions`,
  `total_network_reactions`, `reference_pathways_matched`
- `reference_file`, `reference_module_name`, `critical_issues`, `warnings`,
  `recommendations`, `validation_timestamp`

**`scores.csv`** — one row per `(model, molecule, config, iteration)`, where
`iteration` is `1..3` or `Final`:

```
model, molecule, config, iteration, confidence, recall, precision,
mol_match, recall_75pct, count_75, recall_100pct, count_100, count_total
```

## `figs_data/`

CSV tables extracted for plotting (split into `_part1`/`_part2` where a single
file was too large):

| File(s) | Backs | Key columns |
|---|---|---|
| `fig2a_part1.csv`, `Fig2a_part2.csv` | Fig 2a | `model, molecule, config, iteration, recall, precision, recall_x10, novelty_1minusprecision_x10, count_total` |
| `fig2b_part1.csv`, `fig2b_part2.csv` | Fig 2b | Molecular-property distributions per role: `metric, role, n, mean, std, min, q1, median, q3, max` |
| `fig2c.csv` | Fig 2c | Per-molecule table: `model, method, target, mol_id, role, environment_formed, common_name, iupac_name, formula, inchi, smiles, logp` |
| `fig2d.csv` | Fig 2d | As 2c plus descriptors: `mw, heavy_atoms, hbd, hba, descriptor_status` |
| `fig3_part1.csv`, `fig3_part2.csv` | Fig 3 | Same shape as Fig 2a (`recall / precision / novelty` per run) |

## Reproducing

These are outputs of the pipeline described in the repository root; regenerate
with:

```bash
python pipeline.py all --molecules Glycine --provider claude
```

See [`../CLAUDE.md`](../CLAUDE.md) for the full pipeline, provider selection,
and validation details.
