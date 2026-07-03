# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A multi-agent system built on **AutoGen 0.4.x** that generates chemical synthesis networks from simple feedstock molecules (H₂O, CO₂, NH₃, HCN, etc.) to complex biomolecules through scientifically grounded prebiotic environments (the ChemOrigins framework). A single `SynthesisNetworkAgent` proposes a complete multi-pathway network; a `CriticAgent` scores it; optional research/RAG context informs both. Generated networks are then validated against curated ChemOrigins reference data.

The repository is structured as an **ablation study**: it measures how different research-context sources (Deep Research, MS Discovery, Perfect RAG, or none) and different LLM backends affect synthesis quality.

## Common Commands

```bash
pip install -r requirements.txt        # install (needs rdkit, drfp, torch via deps)

# Unified pipeline CLI (pipeline.py) — three stages, run individually or end-to-end:
python pipeline.py generate --molecules L-Alanine --runs 1 --provider claude   # generate networks
python pipeline.py inchi    --provider claude   # backfill InChI from PubChem
python pipeline.py validate --provider claude   # validate vs ChemOrigins reference
python pipeline.py all      --molecules L-Alanine --provider claude   # generate -> inchi -> validate
python pipeline.py <stage> --help               # per-stage flags

python pubchem_inchi_lookup.py <network.json>   # (still usable standalone; the inchi stage imports it)
```

[pipeline.py](pipeline.py) is a single batch experiment driver (not a unit-test suite). Select what to run with CLI flags (`--molecules`, `--configs`, `--runs`, `--provider`); the full `ABLATION_CONFIGS` / `VALIDATION_CONFIGS` and a `KNOWN_MOLECULES` reference live near the top of the file. All stages auto-resume by skipping already-completed `(molecule, config, run)` combinations and cached outputs.

**Output layout is per-provider** so the stages chain with no manual step: `generate` writes `outputs/{provider}/`, `inchi` writes `outputs_inchi_corrected/{provider}/`, `validate` writes `validation_report/{provider}/`. `{provider}` is the `MODEL_PROVIDER` value (or `--provider` override).

## Selecting the LLM backend

The model backend is chosen at runtime by the **`MODEL_PROVIDER`** env var in `config.env`, resolved in [config/azure_config.py](config/azure_config.py) by `get_high_reasoning_client()`. Each provider has its own client wrapper under `config/` that mimics the `AzureOpenAIChatCompletionClient.create()` interface:

| `MODEL_PROVIDER` | Client | Config module |
|---|---|---|
| `claude` | ClaudeClientWrapper (Claude Opus 4.6) | [config/claude_config.py](config/claude_config.py) |
| `gpt41` | AzureOpenAIChatCompletionClient (GPT-4.1) | [config/azure_config.py](config/azure_config.py) |
| `gpt5.4_openai` | OpenAIDirectClientWrapper (GPT-5.4, direct OpenAI Responses API) | [config/openai_direct_config.py](config/openai_direct_config.py) |
| `gpt5.4_agent_azure` | GPT54AgentAzureClientWrapper (GPT-5.4, Azure AI Projects agent) | [config/gpt54_agent_azure_config.py](config/gpt54_agent_azure_config.py) |

`get_high_reasoning_client()` supports only these four `MODEL_PROVIDER` values (three models: Claude Opus 4.6, GPT-4.1, GPT-5.4); any other value raises `ValueError`. Separately, all base agents call `get_azure_client()` (standard GPT-4o-class workhorse) regardless of provider. When adding a provider: create a wrapper exposing async `create()`, register it in `get_high_reasoning_client()`, and add the display branch in `pipeline.py`'s `print_provider_info()`.

## Environment Configuration

`config.env` (loaded via `python-dotenv`) holds credentials for all providers. Only the keys for your selected `MODEL_PROVIDER` are required; others can be absent. Notable groups:
- **Azure OpenAI** (GPT-4o, the default workhorse): `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_DEPLOYMENT_NAME` (+ `_MINI`)
- **Claude**: `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `CLAUDE_ENABLE_THINKING`, `CLAUDE_THINKING_BUDGET`, `CLAUDE_MAX_TOKENS`
- **GPT-4.1**: `AZURE_GPT41_ENDPOINT`, `AZURE_GPT41_API_KEY`, `AZURE_GPT41_API_VERSION`, `AZURE_GPT41_DEPLOYMENT_NAME`
- **GPT-5.4 (direct OpenAI)**: `OPENAI_DIRECT_API_KEY`, `OPENAI_DIRECT_MODEL`
- **GPT-5.4 (Azure AI Projects agent)**: `AZURE_AGENT_PROJECT_ENDPOINT`, `AZURE_AGENT_NAME`, `AZURE_AGENT_VERSION`
- **Deep Research** (o3-deep-research, optional): `AZURE_DEEP_RESEARCH_ENDPOINT`, `AZURE_DEEP_RESEARCH_API_KEY`, `AZURE_DEEP_RESEARCH_MODEL`
- **Embeddings** (MS Discovery RAG): `AZURE_EMBEDDING_ENDPOINT`, `AZURE_EMBEDDING_API_KEY`, `AZURE_EMBEDDING_DEPLOYMENT`, `AZURE_EMBEDDING_MODEL`, `AZURE_EMBEDDING_API_VERSION`
- **Gemini judge**: `GOOGLE_API_KEY`

## Architecture

### Generation pipeline — [core/network_workflow.py](core/network_workflow.py)

`run_network_workflow(target_molecule, ...)` is the single entry point for generation:

```
load research context (deep research / MS discovery / perfect RAG — from cache or API)
        ↓
SynthesisNetworkAgent  → generates a complete SynthesisNetwork in one call (with context)
        ↓
CriticAgent            → NetworkEvaluation with confidence (0–1)
        ↓
confidence ≥ threshold → accept  |  else retry with feedback (up to max_retries)
        ↓
write NetworkSynthesisResult → outputs/network_{mol}_{ts}_{config}_run{n}[_attempt{m}].json
```

Each retry attempt is saved (`_attempt{m}.json`); the final accepted result is saved without the `_attempt` suffix. `MAX_LLM_RETRIES` (10) guards transient LLM failures inside one attempt. Note this is a **single-shot network generation**, not the older iterative step-by-step loop — there is no `WorkflowManagerAgent`, dynamic-completion, or parallel-synthesis path anymore (those references in older docs are stale).

### Three research/context sources (independent, toggled per ablation config)

1. **Deep Research** (`enable_deep_research`) — literature findings. Live via [agents/deep_research_agent.py](agents/deep_research_agent.py) (`AstroDeepResearchAgent`, OpenAI `responses.create()` with `web_search_preview`), or loaded from cached files in `reports/deep_research_claude/`, `reports/deep_research_gemini/`, `reports/deep_research_gpt5.4/`. `_load_cached_deep_research()` auto-detects JSONL (o3 format) vs. plain text.
2. **MS Discovery** (`enable_ms_discovery`) — embedding-similarity research over a mass-spec/reaction database, loaded in the active path from cached text files (`ms_discovery_cache_file`) by `_load_cached_ms_discovery()` in [core/network_workflow.py](core/network_workflow.py).
3. **Perfect RAG** (`enable_perfect_rag`) — curated, hand-written literature reviews in `reports/perfect_rag/{Molecule}.md` (one file per molecule, shared across runs).

`ABLATION_CONFIGS` in `pipeline.py` enumerates the combinations to compare (selected per run via `--configs`). `naive_approach/` holds prompts/configs for a no-agent baseline.

### Validation subsystem — `agents/validators/`

Run by `pipeline.py validate` (logic lives in [pipeline.py](pipeline.py)), independent of generation. Compares every reaction in a generated network against ChemOrigins reference data:
- [agents/validators/validation_orchestrator.py](agents/validators/validation_orchestrator.py) — `ValidationOrchestrator` coordinates and writes reports
- [agents/validators/chemorigins_validator.py](agents/validators/chemorigins_validator.py) — InChI/similarity matching against reference reactions, best-match by avg(product, reactant) similarity
- [agents/validators/rdkit_similarity.py](agents/validators/rdkit_similarity.py) — RDKit-based molecule/reaction similarity (uses `drfp`)
- [core/chemorigins_loader.py](core/chemorigins_loader.py) — loads/indexes reference JSON

Reference data: `validator/pbmdl-*-{Molecule}.json` (auto-discovered by molecule name). Output: `validation_reports/<file>_validation.json` per molecule plus `attempt_scores.png`. Computes precision + recall across attempts.

### Agents — `agents/`

- `SynthesisNetworkAgent` ([agents/synthesis_network_agent.py](agents/synthesis_network_agent.py)) — the active synthesis agent; emits a full network.
- `CriticAgent` ([agents/critic_agent.py](agents/critic_agent.py)) — scores networks, returns feedback for retries.
- `AstroDeepResearchAgent` ([agents/deep_research_agent.py](agents/deep_research_agent.py)) — literature verification.

### Data models — `models/`

Pydantic v2 models, split by concern:
- [models/schemas.py](models/schemas.py) — core: `Molecule`, `ReactionStep`, `CriticEvaluation`, `DeepResearchReport` + `Citation`, `CompletionAssessment`
- [models/pathway_schemas.py](models/pathway_schemas.py) — network generation: `SynthesisNetwork`, `NetworkReaction`, `SynthesisPathway`, `NetworkEvaluation`, `NetworkSynthesisResult` (used by `network_workflow`)
- [models/validator_schemas.py](models/validator_schemas.py) — validation: `ValidationReport`, `ReactionValidation`, `PathwayMatchResult`, `PathwayMatch`, `ReferenceCitation`

### I/O logging — `core/`

Every LLM call is logged to JSONL for debugging/analysis. `IOLogger` ([core/io_logger.py](core/io_logger.py)) is the base; `validation_io_logger.py` is a specialized variant. Logs land in `logs/io/` and `logs/network_workflow_{ts}_{config}.log`.

## Output & Data Layout

| Path | Contents |
|---|---|
| `outputs/` | generated networks (`network_*.json`) + rendered `*_network.png` |
| `logs/` | per-run workflow logs; `logs/io/` JSONL I/O logs |
| `validation_reports/` | validation JSON + `attempt_scores.png` |
| `validator/` | ChemOrigins reference data (`pbmdl-*.json`) |
| `reports/deep_research_{claude,gemini,gpt5.4}/` | cached deep-research text per molecule |
| `reports/perfect_rag/` | curated literature reviews (`{Molecule}.md`) |
| `naive_approach/` | no-agent baseline prompts/configs |
| `analysis/` | LaTeX report/prompt generation scripts |

## Key Implementation Notes

- **AutoGen 0.4.x** (`autogen-agentchat`, `autogen-ext[openai]`, `autogen-core`) — different API from 0.2.x.
- **Async everywhere** — all agent/workflow methods are `async`; entry points use `asyncio.run(main())`.
- **JSON mode** — agents request structured output (`json_output=True` / `response_format={"type":"json_object"}`); provider wrappers normalize this. Reasoning models (DeepSeek R1, GPT-5) may take minutes — client timeouts are set high (e.g. 600s).
- **Filename matching is fuzzy** — `_find_file_case_insensitive` / `_normalize_name` treat hyphens and underscores as equivalent (`L-Alanine` ↔ `L_Alanine`), used to resolve caches/references by molecule name.
- **Resume-friendly** — both batch scripts scan `outputs/` and skip completed runs, so reruns are incremental.
- When changing `run_network_workflow`'s signature, update its call site in `pipeline.py`'s `cmd_generate()` (the only caller of generation).

## Domain Context (ChemOrigins framework)

Synthesis is grounded in three prebiotic environments; reactions in a network are tagged by environment:
- **Hydrothermal (deep-sea alkaline vents)** — 350–600K, high pressure, iron-sulfur catalysis (greigite, magnetite, pyrite, elemental Fe); CO₂ reduction, reductive amination, pyruvate synthesis.
- **Surface (evaporitic pools & geothermal fields)** — 300–370K, ambient pressure, wet-dry cycles, UV; Strecker synthesis, HCN oligomerization, cyanosulfidic (Powell-Sutherland) pathways; montmorillonite, phosphate/borate minerals, TiO₂.
- **Biochemical (prebiotic assembly)** — variable conditions; peptide/nucleotide assembly and proto-metabolic cycles connecting hydrothermal + surface products into biomolecules.
- **Common feedstocks**: H₂O, CO₂, NH₃, HCN, H₂CO, H₂S, N₂, CH₄, H₂.
