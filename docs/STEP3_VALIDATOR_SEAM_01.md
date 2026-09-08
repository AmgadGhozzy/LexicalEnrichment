# Step 3 Completion Record — Validator Seam (Candidate 1)

> Architectural checkpoint. Behavior-preserving seam established.
> Next work (generation seam) must NOT begin until the 15-word matrix freeze.

```
tests:             50 / 50
behavior changes:  0
shared enum owner: evaluation/lexical_validator.py
hash owner:        evaluation/utils.py
legacy contracts:  preserved
pilot artifacts:   untouched
known unrelated failure: input-builder config reference (quarantined)
```

## What this step did

1. **Pass A — shared enum contract.** Created `evaluation/lexical_validator.py` as
   the single owner of `VALID_REGISTERS`, `VALID_PRIMARY_SENSES`, `VALID_CATEGORIES`,
   and the open-tag semantic bounds (`MIN/MAX_SEMANTIC_TAGS`, `SEMANTIC_TAG_PREFIX`).
   Replaced the three previously-duplicated local declarations:
   `pipeline/phase1_lexical_core.py`, `pipeline/phase_eval_machine.py`,
   `qa/verify_staging_integrity.py`. **No control-flow change.**

2. **Pass B — tri-state artifact validator.** Implemented `LexicalValidator` as the
   canonical deep validator (rule groups: schema / structure / semantics / examples /
   mnemonic / relations / artifact), moving the logic out of
   `artifact_validator.validate_artifact` verbatim. `artifact_validator.validate_artifact`
   is now a pure compatibility wrapper. Diagnostics preserved byte-for-byte.

## Preserved divergence (do NOT unify)

Sharing the enum *sets* is not sharing the *acceptance semantics*:

- `phase1` / `verify_staging_integrity`: a missing enum value is an **ERROR**.
- `phase_eval_machine.evaluate_word`: a missing value is **TOLERATED**; only an
  invalid supplied value is an ERROR.

These are intentionally left distinct. Unifying them is a behavioral migration, out of scope.

## Verified

- Direct `LexicalValidator` unit tests: `evaluation/test_lexical_validator.py` (17).
- Characterization pin: `evaluation/test_validator_characterization.py` (20).
- Utility seam: `evaluation/test_utils.py` (12).
- Importer strict mapping: 1.
- Wrapper == direct-instance equivalence confirmed across valid / SCHEMA_VIOLATION /
  CIRCULAR_DEFINITION / TARGET_WORD_MISSING / MISSING_OUTPUT.
- Hash logic owned by `utils.canonical_hash`; the validator delegates to it (no
  parallel implementation).

## Known unrelated failure (quarantined)

`test_batch_infrastructure.py::test_input_builder_determinism` references a renamed
config. **Pre-existing / unrelated** to this seam. Deliberately NOT fixed here.
