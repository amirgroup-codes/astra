# Prebiotic Synthesis Network — Comparative Evaluation Guide

## Task

You are an expert in prebiotic chemistry and origin-of-life research. You will evaluate **1 synthesis network variants** (Config A) that each attempt to construct a plausible prebiotic synthesis pathway for the **same target molecule** from simple starting materials (H₂O, CO₂, NH₃, HCN, H₂CO, H₂S, N₂, CH₄, H₂).

Each network proposes reactions across three environments:
- **Hydrothermal**: Deep-sea alkaline vents, iron-sulfur catalysis (350–600 K)
- **Surface**: Evaporitic pools, wet-dry cycles, UV photochemistry (300–370 K)
- **Biochemical**: Final assembly of complex biomolecules under prebiotic conditions

Your goal is to **independently evaluate each config**, then **rank all six** from best to worst.

---

## Anti-Bias Protocol

To ensure fair evaluation:

1. **Evaluate each config in isolation first.** Score it fully before reading the next config.
2. **Do not anchor on the first network.** The first config you read is not the baseline — treat all equally.
3. **Do not assume any config is a control or baseline.** Judge purely on scientific merit.
4. **After scoring all six individually, perform a comparative ranking** with explicit justification.

---

## Evaluation Criteria

Score each criterion from **1 (poor) to 10 (excellent)**.

### 1. Chemical Feasibility
- Are the proposed reactions thermodynamically and kinetically plausible?
- Are activation energies reasonable for the stated conditions?
- Are catalysts appropriate and available in the stated environment?

### 2. Pathway Coherence
- Do reaction sequences flow logically from starting materials to the target molecule?
- Are intermediates reasonable and properly connected?
- Is there a clear progression from simple to complex molecules?

### 3. Environmental Consistency
- Are temperature, pressure, and catalyst conditions appropriate for each environment?
- Does the network respect the constraints of each environment (e.g., no UV in hydrothermal vents)?
- Is the transition between environments plausible?

### 4. Mechanistic Detail
- Are reaction mechanisms specified and chemically accurate?
- Is the reasoning for each reaction step well-justified?
- Are side reactions and selectivity considerations addressed?

### 5. Network Completeness
- Does the network cover all necessary intermediates?
- Are multiple pathways provided for redundancy?
- Are starting materials properly justified and prebiotically available?

### 6. Prebiotic Plausibility
- Are the proposed reactions consistent with published prebiotic chemistry literature?
- Are mineral catalysts, energy sources, and concentrations realistic for early Earth?
- Does the network avoid anachronistic reagents or conditions?

### 7. Novelty of Reactions
- Does the network propose creative, non-obvious reaction pathways beyond well-known textbook chemistry (e.g., Miller-Urey, Strecker)?
- Are unconventional or under-explored intermediates introduced?
- Does the network employ novel catalytic strategies or unexpected environmental conditions?

---

## Output Format

For **each config**, provide:

```
### Config [X]

| Criterion                   | Score (1-10) | Justification |
|-----------------------------|-------------|---------------|
| Chemical Feasibility        |             |               |
| Pathway Coherence           |             |               |
| Environmental Consistency   |             |               |
| Mechanistic Detail          |             |               |
| Network Completeness        |             |               |
| Prebiotic Plausibility      |             |               |
| Novelty of Reactions        |             |               |
| **Total**                   |   **/70**   |               |

**Strengths:** ...
**Weaknesses:** ...
```

After evaluating all six configs, provide:

```
## Final Ranking

| Rank | Config | Total Score | Key Differentiator |
|------|--------|-------------|-------------------|
| 1    |        |             |                   |
| 2    |        |             |                   |
| 3    |        |             |                   |
| 4    |        |             |                   |
| 5    |        |             |                   |
| 6    |        |             |                   |

## Comparative Analysis
[Explain what separates the top-ranked config from the others, and identify any systematic patterns across configs.]
```
