# Evaluation Protocol
**Version**: v1.0 | **Date**: 2026-09-01 | **Status**: Active

## Purpose

This protocol defines the three-phase evaluation pipeline used to compare Legacy (`WordsMaster.db`) data against V2 (Phase 1 generated) data for the 200-word stratified golden set. The goal is to answer one question:

> **Does V2 regeneration provide enough improvement over Legacy to justify its cost and risk?**

---

## Evaluation Phases

### Phase A — Machine Evaluation (Automated)

**Script**: `pipeline/phase_eval_machine.py`
**Scope**: Structural validity and contract compliance.

Machine evaluation can determine:
- ✅ Is the JSON schema valid?
- ✅ Are all required fields present and correctly typed?
- ✅ Do enum values (POS, register, primary_sense) conform to the contract?
- ✅ Is the word identity preserved (lemma, POS, CEFR)?
- ✅ Field-level status: `preserved / added / modified / removed / unchanged / not_evaluated`

Machine evaluation **cannot** determine:
- ❌ Whether a definition is linguistically accurate
- ❌ Whether V2's alternative mnemonic is better or worse than Legacy's
- ❌ Whether sense coverage is pedagogically superior

**Output stored in**: `word_evaluations.machine_validation_result`, `structural_score`, `content_completeness`, `preservation_score`, `field_comparison`.

**Gate**: All 200 words must pass before proceeding to Phase B.

---

### Phase B — LLM Judge Evaluation (Blind Comparison)

**Script**: `pipeline/phase_eval_llm.py` (to be built)
**Scope**: Linguistic accuracy and pedagogical quality.

The LLM Judge evaluates Legacy and V2 outputs **independently** (not as a pair initially) then compares them field-by-field. The judge does **not** know which is "Legacy" and which is "V2" during scoring.

**Scoring dimensions** (per `scoring_rubric.md`):
- Definition accuracy (1–5)
- Sense coverage (1–5)
- Naturalness (1–5)
- Learner utility (1–5)
- Pronunciation correctness (1–5, US IPA focus for Phase 1)
- Arabic pedagogical quality (1–5)

**Per-field verdict**:
```
winner: legacy | v2 | tie | insufficient_evidence
improvement: major | minor | none | regression
```

**Phase 1 scope**: Only evaluate fields that Phase 1 produces. Do **not** penalize V2 for missing `examples`, `collocations`, `translations` — those belong to Phases 2–4.

**Output stored in**: `word_evaluations.linguistic_score`, `pedagogical_score`, `generated_quality`, `legacy_quality`, `improvement_score`.

---

### Phase C — Human Calibration (30-word Subset)

**Scope**: Validate LLM Judge accuracy before applying it to the full 200.

A human reviewer evaluates the **same 30 words** using the same rubric, **before** seeing the LLM Judge verdict.

Then we calculate:
- Decision agreement % (Legacy vs V2 winner)
- Score correlation (Human score vs LLM score)
- Regression detection (cases where LLM and Human strongly disagree)

**Acceptance threshold**: Decision-level agreement ≥ 85% before running Judge on full 200.

If agreement < 85%, the rubric is revised and Phase C is repeated on a new 30-word subset.

---

### Phase D — Decision Engine

**Script**: `pipeline/phase_eval_decision.py` (to be built after Phase C)
**Scope**: Apply `decision_policy.md` rules to produce KEEP / ENRICH / REGENERATE / MANUAL_REVIEW for each word.

---

## Execution Order

```
STEP 4.5  freeze_baseline.py        → data/evaluation/legacy_baseline_200.json
STEP 5    phase_eval_runner.py      → word_evaluations (raw_generated_payload)
STEP 6    phase_eval_machine.py     → word_evaluations (machine scores)
STEP 6.5  [review machine report]   → human review of gate metrics
STEP 7    [human calibration 30]    → human scoring on 30-word subset
STEP 8    phase_eval_llm.py         → word_evaluations (linguistic scores)
STEP 8.5  [calibration check]       → agreement % validation
STEP 9    phase_eval_decision.py    → word_evaluations (decision)
STEP 10   [final ROI report]        → docs/evaluation/golden_set_evaluation_report.md
```

---

## Constraints

- **No overwrite of Legacy DB during evaluation**
- **No write to core V2 tables** (`words`, `word_senses`, `pronunciations`) from evaluation scripts
- **Every run is identified by** `run_id` + `evaluator_version`
- **Idempotent**: Re-running a script on existing data must not create duplicates (`UNIQUE(run_id, word_id)`)
- **Phase 1 only in this round**: No Phase 2–4 fields are generated or evaluated now
