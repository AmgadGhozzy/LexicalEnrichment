# 09: Deterministic IELTS mapping execution (BT-07)

**What to build:** the executed 1–6 cascade over all 1,022 IELTS rows
using the locked 02 folding, 03 POS policy, and BT-03 #2-vs-#3 rule —
producing the versioned mapping artifact with full per-row
provenance and verified counts against the 678/34/276/34/0
baseline (mechanical deltas only, explained row by row).

**Blocked by:** 03 (mapping rule), 04 (identity), 07 (schemas).

**Status:** resolved

**Spec ref:** spec §2 (IELTS cascade, evidence-only, gated pool);
wayfinding 05.

## Execution record

- New module `evaluation/ielts_cascade.py` (reads frozen artifact
  as input; never modifies it): BT-04 normalizer + BT-03
  first-match order + BT-07 `mapping_provenance` shape;
  classification creates nothing and overwrites nothing.
- New tests `evaluation/test_ielts_cascade.py`: 10 passed
  (exact/case-fold/diff-POS/unmappable/multiword-short-circuit/
  new/empty/counts-shape, universe folding with composite drop,
  records insert cleanly into `mapping_provenance`). One
  fixture-only bug fixed (universe source); module correct.
- Full execution over 1,022 frozen rows → NEW artifact
  `.scratch/lexical-migration-build/output/ielts_mapping_v2.json`
  (input hash pinned, rule order recorded, per-row provenance):
  678 / 0 / 34 / 34 / 276 / 0 — identical to baseline,
  mechanical delta zero, every row classified exactly once.
- Frozen `evaluation/forensic_audit/ielts_mapping.json`
  byte-untouched. No canonical field overwritten; duplicates kept
  as topic rows; multiwords quarantined unminted; 276 emitted as
  candidates only.
- Suite: 99 passed. Pre-existing fixture failure unchanged.

- [ ] All 1,022 rows classified exactly once; counts verified
- [ ] No canonical field overwritten by any IELTS value
- [ ] Duplicates kept as separate topic rows; multiwords routed
  to quarantine, none minted as identities
- [ ] 276-row pool emitted as candidates only (creation is BT-10
  scope or later, never here)
