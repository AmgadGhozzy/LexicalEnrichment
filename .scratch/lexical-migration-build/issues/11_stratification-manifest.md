# 11: Pilot stratification decision + frozen manifest (BT-10)

**What to build:** the manifest-spec decision (strata, quotas,
seed, allocation over frequency/version, CEFR, POS, IELTS
overlap, and locked lexical characteristics) followed by the
frozen pilot manifest (candidate IDs, snapshot hash, algorithm,
seed, exclusions/replacements, manifest hash) — excluding Golden
160, prior experiment words, and all quarantined/unresolved/
malformed candidates.

**Blocked by:** 06 (frequency), 09 (mapping), 10 (quarantine).

**Status:** resolved

**Spec ref:** spec §7 (pilot); chain 01+08 → stratification
decision → manifest → pilot.

## Execution record

- New module `evaluation/pilot_manifest.py` (pure functions; DB
  access is the caller's read-only concern): (cefr,pos) cells over
  RAW master values (verified master POS == canonical 11-tag set
  verbatim — no remapping invented), proportional allocation with
  floor 2 + largest remainder, seeded shuffle, freeze with
  canonical hash. CEFR carried as evidence-label stratum ONLY;
  manifest stamps cefr_stratum_authority=OPEN with mandatory
  re-stratification after Gate A licensed EVP.
- Decision locked: N=1000, seed 730011; universe = master only
  (zero approved IELTS candidates exist yet — stated);
  quarantined classes staging-side, absent from universe by
  construction.
- New tests `evaluation/test_pilot_manifest.py`: 7 passed
  (allocation sums, tiny cells, determinism, exclusions, overlap
  flag, OPEN flag, hash stability/instability).
- Frozen `output/pilot_manifest_v1.json` (hash f76443bac76a9883):
  1,000 entries; exclusions verified — 0/160 golden, 0/100 prior
  (141 EXP keys collapse to 100 distinct ids, all covered),
  in-range 14–7294; spread A1 136 / A2 142 / B1 146 / B2 285 /
  C1 270 / C2 21 (evidence labels, non-authoritative); 89
  IELTS-overlap flagged. Re-run reproduces the hash exactly.
- DB contact: three read-only SELECT passes
  (`mode=ro` URI: columns, universe ×2 incl. rerun check). Zero
  writes, zero schema reads beyond PRAGMA, frozen files
  byte-untouched. No pilot execution here (BT-12 scope).
- Suite: 111 passed. Pre-existing fixture failure unchanged.

- [ ] Strata/quotas/seed/allocation explicitly decided (no
  convenience strata)
- [ ] Manifest frozen with hash; exclusions verifiable
- [ ] OPEN: CEFR-stratum shape contingent on BT-01 (Gate A) —
  manifest must not assume canonical CEFR before it closes
- [ ] No pilot execution in this ticket (BT-12 scope)
