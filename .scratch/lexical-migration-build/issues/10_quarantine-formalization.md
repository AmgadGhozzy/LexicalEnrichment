# 10: 727 + multiword quarantine formalization (BT-08)

**What to build:** quarantine records for 100% of the 727 (with
per-class review state, never bulk-promoted, never deleted) and
the 34 IELTS multiwords with topics attached — verified complete
against the forensic decomposition, with the 692-gap and vintage
items carried as stated BLOCKED/OPEN notes, not resolved here.

**Blocked by:** 07 (schemas), 09 (mapping execution).

**Status:** resolved

**Spec ref:** spec §3 (quarantine, 727/vintage, OPEN gap);
wayfinding 04, 10.

## Execution record

- New module `evaluation/quarantine.py` (metadata layer only; no
  DB read/write, no staging opens): class-level 727 records with
  per-class criteria + review state + forensic provenance
  (count-mismatch raises), per-row multiword builder (count ≠ 34
  raises; non-whitespace leak raises), `assert_no_promotion`
  invariant (identity-id fields or approved states raise).
- Scope boundary enforced: per-ROW 727 materialization
  (source_row_id enumeration from staging) is BLOCKED on Gate B —
  ingesting rows from an unlocated vintage into any store would
  launder provenance. Stated in every class record, not done.
- New artifact `output/quarantine_v1.json`: 727 class-complete
  (121/571/32/3) + 34 per-row multiwords with topics.
- New tests `evaluation/test_quarantine.py`: 5 passed (727 sum,
  review states, no-promotion incl. negative cases, 34/34 topics
  with no leakage, BT-07 schema fit with zero identities minted).
- Suite: 104 passed. Frozen artifacts untouched; nothing
  promoted, nothing deleted. Pre-existing fixture failure
  unchanged.

- [ ] 727/727 accounted; 34/34 multiwords preserved as quarantine
  evidence with topics attached — never split into identities,
  never minted as single-word records
- [ ] No quarantined row promoted without its applicable review
- [ ] BLOCKED: vintage entry rule awaits BT-02; OPEN: 692 gap
  awaits BT-02 reconciliation
- [ ] Quarantine completeness asserted by test, not prose
