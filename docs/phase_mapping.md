# Lexical Enrichment Engine: Legacy → V2 Migration Matrix

This document maps the architectural components, schemas, and prompts from the V1 Legacy Monolith (`DictionaryEnrichment.py`) to the V2 Staged Pipeline. It explicitly identifies what was migrated, what was deferred to later phases, and what was deliberately modified to enforce deterministic invariants.

## 1. Core Architecture & Workflow Mapping

| Legacy Feature | V2 Phase Mapping | Status / Decision |
| :--- | :--- | :--- |
| `WordsMaster.db` | Immutable Source | **LOCKED**. Treated as read-only. `phase0_audit_import.py` now enforces strict import rules (fails on missing POS or invalid CEFR instead of silently defaulting). |
| `DictionaryEnrichment.py` | V2 Phase 1-8 Pipeline | **REPLACED**. The monolithic script is kept only as a reference. V2 breaks extraction into specific deterministic phases. |
| SQLite Schema (`words.db`) | `db/schema.sql` | **REDESIGNED**. Normalized into 16 tables: `words`, `pronunciations`, `word_senses`, `field_versions`, `examples`, `collocations`, `sense_translations`, etc. |
| In-memory error handling | Pre-write validation | **ENHANCED**. `phase1_lexical_core.py` runs deterministic checks *before* DB writes. Failures rollback transaction and record failed `enrichment_runs`. |

## 2. Prompt & Instructions Migration

| Legacy Component | V2 Phase 1 Component | Status / Decision |
| :--- | :--- | :--- |
| `SystemPrompt_Enhanced.md` | `prompts/system/lexical_core.md` | **EXTRACTED**. Rules about POS strictness, Half-Tashkeel for Arabic, and IPA slashes are migrated. Rules for examples, word families, and translations are deferred to Phases 2-4. |
| `BatchUserPrompt.md` | `prompts/tasks/lexical_core.md` | **EXTRACTED**. The batch loading logic (`{{BATCH_JSON}}`) is maintained. The specific sense-extraction instructions are adapted for Phase 1. |
| POS & CEFR overrides by LLM | Enforced Parity Check | **FIXED**. V2 requires the model to echo `lemma`, `pos`, and `cefr_level` and strictly matches them to the input. The LLM is forbidden from re-categorizing the Source POS. |
| `aiConfidence` | `aiConfidence` (Word-level) | **MAPPED**. V1 placed it in the root schema. V2 outputs it in Phase 1 and saves it as `model_self_confidence` inside the `field_versions` audit trail. It is considered untrusted metadata and does not affect the deterministic QA decision. |

## 3. JSON Schema Migration (`StructuredOutput_Enhanced.json`)

### ✅ Migrated to Phase 1 (`lexical_core.json`)
*   `id`, `difficultyScore`, `category` (Word-level attributes).
*   `phoneticUs`, `phoneticUk` (Enforced NO slashes `/ /`).
*   `phoneticAr` (Enforced Half-Tashkeel).
*   `definitionEn`, `definitionAr`, `usageNote`, `primarySense`, `semanticTags`, `register` (Moved to Sense-level under `senses` array).
*   `mnemonicAr` (Enforced formatting: `""` only, no `()` or `[]`).
*   `is_primary` (V2 architectural addition: Exactly ONE primary sense enforced by Partial Unique Index and Python validation).

### ❌ Excluded from Phase 1 (Deferred to Later Phases)
*   `translit`: Explicitly banned from Phase 1. Will be part of Phase 4 (`sense_translations`).
*   `examples`: Deferred to Phase 2 (Pedagogy).
*   `collocations`, `synonyms`, `antonyms`, `relatedWords`, `wordFamily`: Deferred to Phase 3 (Relations).
*   `arabicAr`, `frenchFr`, `germanDe`, `spanishEs`, `chineseZh`, etc.: Deferred to Phase 4 (Translations).

## 4. Specific Business Rule Enforcements in Phase 1

1.  **Exactly 1 Primary Sense:** V2 enforces `sum(is_primary) == 1`.
2.  **POS Semantics Test:** Words like `get (noun)` and `set (adj)` will forcefully test the LLM's adherence to the source POS. Mismatches will trigger QA failures.
3.  **No `translit` Bleeding:** Validations ensure the LLM does not hallucinate the `translit` field early.
4.  **JSON ↔ SQLite Parity:** `qa/verify_staging_integrity.py` actively asserts that all generated fields in the LLM JSON structurally map correctly into the SQLite tables without data loss.
