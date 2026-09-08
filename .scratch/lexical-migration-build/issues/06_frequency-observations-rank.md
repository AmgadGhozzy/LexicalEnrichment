# 06: Versioned frequency observations + dense rank (BT-05)

**What to build:** versioned frequency-observation recording
(wordfreq Zipf; source/version/lang/metric/observed_at, corpus
identity kept separate) with deterministic dense-rank derivation
per pinned version (ties share rank; alphabetical lemma is
display-order only) — verified on pinned fixtures, legacy
rank/frequency preserved untouched and never consumed.

**Blocked by:** 04 (identity folding + key).

**Status:** resolved

**Spec ref:** spec §2 (frequency); wayfinding 01 (Zipf canonical,
provenance, dense rank, legacy preserved, stable IDs).

## Implementation record

- New module `evaluation/frequency.py` (pure functions; no I/O, no
  network, no DB, no live wordfreq fetch): `build_observation`
  (pins source/version/lang/metric/observed_at; corpus_id kept
  separate; rejects missing pins and non-finite Zipf),
  `derive_ranks` (single-scope dense rank; ties share; alpha
  display-only; input-order independent; explicit supersede),
  `ranks_by_scope` (upgrades add scopes, history never rewritten).
- Hardened during execution: `derive_ranks` REFUSES mixed scopes
  with ValueError instead of silently merging (the original draft
  merged — caught on self-review before tests ran).
- New tests `evaluation/test_frequency.py`: 11 passed (dense ties,
  order independence, no unique ordinals, mixed-scope refusal,
  scope partition, supersede, pin/zipf/key validation, no-DB-
  footprint assertion on the module source).
- Suite: 66 passed (new + identity + provenance + validator +
  utils). Pre-existing `test_input_builder_determinism` failure
  unchanged (missing fixture), out of scope.
- Scope held: recording + derivation on pinned fixtures only.
  Live wordfreq sourcing is execution scope, not this ticket.
  Legacy rank/frequency columns untouched (module cannot address
  a database — asserted in-test).

- [ ] Observations self-describe version; upgrades add versions
- [ ] Dense rank deterministic per pinned version on fixtures
- [ ] No unique-ordinal ranks; no id=rank resurgence
- [ ] Legacy rank/frequency columns byte-identical before/after
