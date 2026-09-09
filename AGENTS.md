# AGENTS.md — LexicalEnrichment

## Repo map (two systems, not one pipeline)
- `pipeline/` = System A (production engine, mostly sleeping): `phase0_audit_import.py` ETL `WordsMaster.db` → `data/staging/LexicalStaging.db`, `phase1_lexical_core.py` senses gen (hardcoded 10 lemmas: bank/right/record/... — does NOT scale), `llm_provider.py` = only `VertexAIProvider` wrapper for A.
- `evaluation/` + `evaluation_runner.py` (root) = System B (active batch/eval): online runner, `batch_runner/input_builder/importer/inspector/comparison`, outputs to `evaluation/experiments/EXP-*/`. Uses `google.genai` directly, NOT `llm_provider.py`.
- Shared-only modules: `evaluation/utils.py` (paths, `canonical_hash`, golden-gated I/O) and `evaluation/lexical_validator.py` (enum contracts). Do not cross-import anything else between A/B.
- Canonical schemas: prod target `db/schema.sql` (16 tables); gen schema `evaluation/prompts/schemas/lexical_output.v1.json`; legacy System A schema `config/schemas/lexical_core.json`. Canonical prompt: `evaluation/prompts/lexical_enrichment_final.txt` (+ `evaluation/configs/gemini_flash_final_batch.json`). Deleted v1.0/v1.1 prompts must not be resurrected.
- `dicPyImp/` = legacy Colab/SQLite cleanup scripts for `WordsMaster.db` table `wordsMaster` (read-only reference, do NOT re-run blindly): `Dic_Enrichment_extracted.py` (WordNet family/category + 4-stage re-rank + levels/units builder), `DifficultyScore.py`, `FinalClean.py`, `LEX-CATEGORY.py`, `PosConverter.py`.

## Freeze / do-not-touch
- `golden_set/golden_v2.json` (160 entries, sha256 `2a179128…2821` in `golden_set/manifest.json`) + `evaluation/experiments/EXP-*/raw` + manifests: immutable evidence. Runners abort on hash/count mismatch — never edit to "fix" a mismatch.
- `google-cloud-key.json`, `*.db`, `.env` are gitignored — never commit, never overwrite `WordsMaster.db` / staging DBs in place; always backup first (`*_backup_*.db` pattern used by dicPyImp scripts).
- Current governance lock: migration wave-1 EXECUTED 2026-09-08 under explicit human EXECUTE decision (1,384 field-level cells into `WordsMaster.db`, audit `migration_audit_2026_001` 1,384 rows, rollback point `WordsMaster_backup_20260908T235840Z.db`; frozen reference `Baseline-PostMigration-001` in `.scratch/lexical-migration-build/output/migration_readiness/baseline/`). Lock stays ON: NO new migration wave, NO 8K run, NO schema/model-matrix comparison without a NEW governance decision. Allowed now: Ticket 17 CLOSED (DESIGN VALIDATED / RULES FROZEN — deterministic field triage v0.1+C1, 57 tests, sample-300 PASS; quotation micro-bug logged as known limitation); Ticket 18 EXECUTED 2026-09-08 (READ-ONLY full-triage PASS: 65,700 records, manifest sha `8614274b…05d090`, 0 anomalies, DB bytes+hash unchanged vs baseline; map in `output/triage/`). Lock stays ON: NO repair/generation/promotion wave without a NEW governance decision. Manual review of the 3 CEFR flags + G2-blocked `billion/num` + 8 legacy-only cards (evidence in `output/migration_readiness/verification/exceptions_evidence.json`; never auto-modify). Post-18 rulings locked: remediation scope = 609 LLM cells ONLY (597 examples + 6 syn + 6 ant; translations/mnemonic/definition/arabic/collocations KEEP; sense MANUAL; billion BLOCKED; watch-alone-is-not-defect); proposed as Ticket 19 (EXECUTED 2026-09-09: candidates+evaluation+audit for 609 scope — 595 cells with verdicts, 14 unevaluated, 5 antonym no-ops pre-marked, 0 canonical writes; evidence in `output/EXP-SEEDED-609/`). Canonical writes since baseline: 1,948 cells over 2 waves (wave-1: 1,384; wave-2 Ticket 20 EXECUTED 2026-09-09: 564 verified = 557 examples + 7 relations, audit `migration_audit_2026_002`, rollback `WordsMaster_backup_20260909T164125Z.db`; 5 no-ops honored; Ticket 20 CLOSED-VERIFIED with post-closure evidence (frozen `Baseline-PostMigration-002`, protected-cols 0-drift vs wave-1 backup, full-7300 regression PASS: 557/557+7/7 remediations verified, 40 residual flags = adjudicated set exactly, relations 0). Lock stays ON: NO further wave without a NEW governance decision; residual queues are REVIEW-ONLY, never auto-work. Derived layer Ticket 21 EXECUTED 2026-09-09 (specs `derived/schema.sql` + `add_word_protocol.md`; artifacts `output/derived/` self-audit PASS (v1.1: hash file-vs-logical documented + `ielts_unmapped.json` added for 34 multiwords, 7 prior artifacts byte-identical, manifest self-consistent 9 files; evidence 7,300, oxford 5,831, IELTS 686 matched, intersections reconciled, zero enrichment copied; canonical untouched; owner final sign-off 2026-09-09: APPROVED — APP-READY · CANONICAL-SAFE · GOVERNANCE-CLOSED).

## Field rules (audit decisions — do not re-litigate)
- `id` = stable identity, never recomputed. `rank` = derived ordinal from versioned frequency, never `id = rank`. `dicPyImp` Stage 4 (`id=rank` rebuild) is a legacy anti-pattern — do NOT repeat.
- Frequency source of truth is `wordfreq` zipf (+ version/lang recorded as `frequency_source/version/metric`); legacy `rank`/`frequency 1–6`/`CEFR` provenance is unknown → VERIFY, never trust blindly. New word: normalize → dedupe on `(lemma,pos)` → `wordfreq` observation → derived rank → CEFR from lexicon (or flagged inferred) → `difficultyScore` → assign `unitId` (curriculum bucket, reassignable, NOT rank order). `rank != CEFR != unit`.
- IPA: store WITHOUT slashes (`verify_staging_integrity.py`, `phase1.validate_response`). If `phonetic_uk IS NULL` → fallback `phonetic_uk = phonetic_us` with `phonetic_uk_source='fallback_from_us'`; if source gave UK → `'dictionary'`. Schema semantic: `phonetic_uk=null` means "same as US", not missing. If US==UK text, keep both rows (variants), do not dedupe away.
- `syllabify`: monosyllabic / 3–4-letter words with no split stay `NULL` (presentation rule). Never invent `c•a•t`. Keep `syllable_count=1` deterministic (syllabify `•` split, else vowel-group estimator); no LLM for syllables.
- `difficultyScore`: keep formula as-is (`dicPyImp/DifficultyScore.py:calculate_score`): `raw = lo + range*rank_position + pos_delta + syllable_delta`, clamped to `CEFR_BOUNDS (A1 2-5, A2 3-6, B1 4-7, B2 5-7, C1 7-9, C2 8-10)`. Only fix scores outside bounds (`analyze()`); run `self_test()` before any DB touch. Open question is whether score adds signal over CEFR+frequency — answer via forensic, not redesign.
- Examples = biggest confirmed problem: legacy `FinalClean.classify_examples` mapped CEFR by sentence word-count (wrong) and 14.8% of 43,800 cells fail exact-lemma check. Regenerate; structural pass ≠ quality. New examples must: contain exact lemma token (`contains_target` in `lexical_validator.py`), match POS+sense, natural English, CEFR-appropriate (NOT length-based). Baseline 3 high-quality examples, not 6; 4th/5th only if polysemy needs it.
- 727 extras: UNPROVEN. Do not quarantine/delete. Required match report first: per extra `(lemma,pos,cefr)` vs 7300 → counts of `X=exact lemma+POS / Y=same lemma diff POS / Z=genuinely new / W=malformed` (incl. `the→noun`, `to→verb` suspects).
- `mnemonic_ar`/`definition_ar`/`definition_en`: human-gated. Validator only rejects generic-null/empty/brackets — cannot judge hook-vs-paraphrase. Legacy `MNE=5` beat V2 `MNE=0`; never ship schema-pass as quality-pass. Translations ×10: keep + sample-audit, no blind regen.

## Validator contracts
- Single owner: `evaluation/lexical_validator.py` `VALID_REGISTERS`/`VALID_PRIMARY_SENSES`/`VALID_CATEGORIES` (+ tag rule 3–5 `#`-prefixed). Must stay in lockstep with both JSON schemas — enforced by `evaluation/test_validator_characterization.py::test_enum_sets_match_schema`.
- Missing enum = ERROR in `phase1_lexical_core.validate_response` and `qa/verify_staging_integrity.py`; TOLERATED in `phase_eval_machine.evaluate_word` (only invalid value errors). Do not unify.
- `LexicalValidator` is artifact-only (ERROR/FLAG/PASS, messages byte-for-byte stable); DB audit is only `qa/verify_staging_integrity.py`. `artifact_validator.py` is a compat wrapper.

## Commands (Windows: use `python`, not `python3`)
- Tests: `python -m pytest evaluation/test_lexical_validator.py evaluation/test_utils.py evaluation/test_batch_infrastructure.py` ; single: `python -m pytest evaluation/test_validator_characterization.py -k <name> -q`.
- Online eval: `python evaluation_runner.py --config <file-in-evaluation/configs> --mode smoke` (5 stratified) or `--mode full` (160); `--resume EXP-...` reuses manifest, mismatched config aborts.
- Staging audit: `python qa/verify_staging_integrity.py [run_id]` (checks 1-primary-sense, IPA slashes, tags, `field_versions`, JSON↔SQLite parity).
- Batch: `python -m evaluation.batch_input_builder --config <cfg> --experiment-id <id>` then `python -m evaluation.batch_runner --config <cfg>`. No resume/retry/cost-log — do not scale to 500+ without fixing.
- `pipeline/phase0_audit_import.py:21` `SOURCE_DB` path is stale (`...\DictionaryEnrichment\LexicalEngine\...`); point it at repo-root `WordsMaster.db` explicitly, and `phase0_preflight.py` is legacy probe only.

## Windows / encoding gotchas
- Always `$env:PYTHONIOENCODING='utf-8'` and `open(..., encoding='utf-8')` for Arabic/IPA/Chinese; `cp1252` terminal misreads clean UTF-8 as `?`/`�` (see `DATA_TRUST_MATRIX.md`). Never "fix encoding" based on console output — verify bytes first.
- Vertex auth priority in `pipeline/llm_provider.py`: `GOOGLE_APPLICATION_CREDENTIALS` file → `GCP_SERVICE_ACCOUNT_KEY` string → hard fail. Defaults: project `gen-lang-client-0841388254`, location `us-central1` (see `.env.example`). `evaluation_runner.py` relies on ADC/project from config instead.
- Batch JSONL transport strips `$schema`/`schema_version` keys (`_strip_schema_metadata`) — Vertex `Schema` proto rejects them. Keep them in canonical schema file, stripped only on send.

## Agent skills

### Issue tracker

Local markdown tracker under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical defaults (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context (`CONTEXT.md` + `docs/adr/`). See `docs/agents/domain.md`.
