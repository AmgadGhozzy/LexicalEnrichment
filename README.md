# LexicalEnrichment

Generative lexical enrichment of English vocabulary — from raw word lists to a CEFR-annotated, curriculum-ready lexical database, using Google Gemini (Vertex AI) with deterministic validation.

Targets a rich per-word record: lemma + POS, senses, IPA, syllabification, frequency (wordfreq zipf), derived difficulty score, CEFR level, curriculum unit mapping, examples (exact-lemma enforced), and Arabic mnemonics/definitions.

## Architecture — two systems, not one pipeline

| | System A — Production Engine | System B — Evaluation / Batch |
|---|---|---|
| **Location** | `pipeline/`, `config/`, `db/` | `evaluation/`, `evaluation_runner.py` |
| **Purpose** | Generate rich lexical DB per `db/schema.sql` (16 tables) | Measure compliance, run online + batch generation experiments |
| **LLM access** | `pipeline/llm_provider.py` (`VertexAIProvider`) | `google.genai` directly |
| **Output** | `data/staging/LexicalStaging.db` | `evaluation/experiments/EXP-*/` (per-word JSON/JSONL) |
| **Status** | Partially sleeping (smoke on 10 hardcoded lemmas; ETL imported 8,027 words) | **Active** (online runner + batch, frozen 160-word golden) |

The two systems share only `evaluation/utils.py` (paths, canonical hashing) and `evaluation/lexical_validator.py` (enum contracts). They do **not** cross-import anything else.

## Repo layout

```
pipeline/        System A: ETL, senses generation, LLM provider
evaluation/      System B: runners, batch infra, validator, tests, experiments
qa/              staging integrity audit
prompts/         canonical system/task prompts
config/          canonical schemas + eval configs
db/              production schema (16 tables)
golden_set/      frozen golden v2 (160 entries + manifest)
dicPyImp/        legacy Colab/SQLite reference scripts (read-only)
docs/            ADRs, eval protocols, audits
data/            raw sets + staging DB
```

## Key contracts

- **Canonical schema**: `evaluation/prompts/schemas/lexical_output.v1.json`
- **Canonical prompt**: `evaluation/prompts/lexical_enrichment_final.txt`
- **Validator**: `evaluation/lexical_validator.py` — single owner of enum contracts, enforced in lockstep with the JSON schemas by characterization tests.
- **Golden set**: `golden_set/golden_v2.json` (160 entries) + `manifest.json` — immutable evidence; runners abort on hash/count mismatch.
- **Governance**: no 8K run, no production migration, no schema/model-matrix comparison until the content-QA gate passes.

## Commands

```
# Tests
python -m pytest evaluation/test_lexical_validator.py evaluation/test_utils.py evaluation/test_batch_infrastructure.py

# Online evaluation (smoke = 5 stratified, full = 160)
python evaluation_runner.py --config <file-in-evaluation/configs> --mode smoke
python evaluation_runner.py --config <file-in-evaluation/configs> --mode full

# Staging integrity audit
python qa/verify_staging_integrity.py [run_id]

# Batch
python -m evaluation.batch_input_builder --config <cfg> --experiment-id <id>
python -m evaluation.batch_runner --config <cfg>
```

## Pipeline principles

- `id` is stable identity; `rank` is a derived ordinal from versioned frequency — never `id = rank`.
- Frequency source of truth is `wordfreq` zipf (version/lang recorded); legacy `rank`/`frequency 1–6`/`CEFR` provenance is unknown and verified, never trusted blindly.
- New word flow: normalize → dedupe on `(lemma, pos)` → wordfreq observation → derived rank → CEFR from lexicon → difficulty score → assign `unitId`. `rank != CEFR != unit`.
- IPA stored without slashes; `phonetic_uk = NULL` means "same as US", not missing.
- Examples must contain the exact lemma token and match POS + sense; baseline is 3 high-quality examples (not 6).
- `difficultyScore` keeps the legacy formula (`dicPyImp/DifficultyScore.py`) clamped to CEFR bounds.

## Status

- Content-QA gate is **open** — that is the current focus. Only read-only forensics (`727_duplicate_pos_forensics`, `DifficultyScore_forensics_v2`, `Legacy_examples_quality_sample`) are in progress.