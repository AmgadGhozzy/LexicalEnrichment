# 03: #2-vs-#3 machine-testable mapping rule (BT-03)

**What to build:** the locked, machine-testable rule distinguishing
cascade #2 (NORMALIZED_LEMMA_EXACT) from #3
(SAME_LEMMA_DIFFERENT_POS), proven against the 1,022-row artifact —
so the two classifications can never overlap and IELTS mapping
execution has an unambiguous input.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Spec ref:** spec §3 (OPEN blocking verification item); wayfinding
05 (cascade, classification ≠ creation); 02 (folding), 03 (POS).

## Locked rule (verified 2026-09-06, read-only over `ielts_mapping.json`)

Order of evaluation per IELTS row (first match wins):

1. `#4 MULTIWORD` if the normalized form contains internal
   whitespace (per 02 hyphen rule).
2. `#5 NEW_SINGLE_WORD` if no canonical candidate exists.
3. `#2 NORMALIZED_LEMMA_EXACT` if the normalized lemma matches but
   the IELTS POS is absent/empty or unmappable to the canonical
   11-tag enum via the locked 1:1 map
   (noun→noun, adj→adj, verb→verb, adv→adv).
4. `#1 NORMALIZED_LEMMA_POS_EXACT` if the mapped POS is held by the
   lemma's canonical identities.
5. `#3 SAME_LEMMA_DIFFERENT_POS` if the mapped POS is present but
   not held (never overwrites canonical POS).
6. `#6 UNRESOLVED_MALFORMED` otherwise.

Mechanical verification on all 1,022 artifact rows: #1=678, #2=0,
#3=34, #4=34, #5=276, #6=0 — identical to the audited baseline,
overlaps=0. Whitespace separates multiwords 34/34 with 0 leakage
into other classes. #2 fires zero times on this source (every
IELTS row carries a comparable POS) and is retained as a
deterministic vacuous class for POS-less future sources — not
removed, not merged into #3.

- [ ] #2 vs #3 rule stated in testable form (absent/non-comparable
  POS vs explicitly present differing POS, or artifact-proven better)
- [ ] Rule verified mechanically against the artifact; overlaps = 0
- [ ] 678/34 baseline disposition stated (hold or deterministically revise)
- [ ] BT-07 unblocked on the rule side (still needs BT-04, BT-06)
