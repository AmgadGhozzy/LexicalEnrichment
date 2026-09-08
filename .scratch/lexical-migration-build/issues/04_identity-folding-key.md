# 04: Identity folding + key implementation and tests (BT-04)

**What to build:** a tested deterministic normalizer implementing the
locked folding contract (trim, lowercase, NFC, single-space,
diacritics preserved; hyphen/whitespace/apostrophe rules;
possessive→base; lemma-level; names/brands excluded) plus the
`(normalized_lemma, canonical_pos)` key builder under the locked
11-tag enum (one POS per identity, composites rejected) — with unit
tests covering hyphen, whitespace, apostrophe, and diacritics cases.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Spec ref:** spec §1; wayfinding 02 (full contract), 03 (enum, one
POS, dependency contract).

## Implementation record

- New module `evaluation/identity.py` (pure string functions, no
  I/O, no DB): `normalize_lemma`, `is_single_word_candidate`,
  `build_key`, locked `CANONICAL_POS` frozenset.
- New tests `evaluation/test_identity.py`: 16 passed
  (folding incl. NFC/diacritics/curly-apostrophe, admissibility,
  key shape, composites refused, enum lockstep against both
  schema files).
- Fixed during execution: curly-apostrophe folding targeted
  literal backslash sequences instead of U+2018/19/02BC
  (caught by the new test, fixed via shared `_APOSTROPHES` set).
- Pre-existing suite: 30 passed, 1 failed —
  `test_input_builder_determinism` fails on a missing config
  fixture (`gemini_flash_v1.1_batch_pilot.json` not found),
  unrelated to this ticket (new files only, no existing imports
  touched). Left as-is; not this ticket's scope to repair.
- Possessive→base kept narrow (trailing `'s` only); internal
  apostrophes preserved. Names/brands exclusion stays at the
  admission layer — the normalizer performs no entity detection.

- [ ] Folding implements every locked sub-rule, nothing invented
- [ ] Key builder enforces 11-tag enum + single POS; composites refused
- [ ] Unit tests green incl. hyphen/whitespace/apostrophe/diacritics
- [ ] Zero-derivation legitimacy NOT judged here (deferred to 03
  adjudication at execution time)
