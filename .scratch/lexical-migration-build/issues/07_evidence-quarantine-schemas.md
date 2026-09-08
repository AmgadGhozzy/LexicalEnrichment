# 07: Evidence and quarantine schemas + provenance discipline (BT-06)

**What to build:** the physical schemas for versioned frequency,
CEFR-evidence (+ canonical value), IELTS-evidence (+ derived-only
`is_ielts` projection), multiword/727 quarantine records, and
mapping provenance — with append-only provenance, immutable
snapshot identity, and the additive-alongside-legacy layout. No
CEFR canonicalization runs here (awaits BT-01); no staging rows
migrated here (awaits BT-02).

**Blocked by:** 04 (identity folding + key).

**Status:** resolved

**Spec ref:** spec §2 (evidence model, `is_ielts`), §3
(quarantine contents), §6 (provenance, additive mechanics);
wayfinding 09, 10.

## Implementation record

- New module `evaluation/evidence_schema.py` (DDL + INSERT-only
  helpers; no UPDATE/DELETE helper exists, asserted in-test):
  `lexical_identity` (composite PK, 11-tag CHECK),
  `source_snapshot` (immutable registry), `lexical_frequency`
  (composite PK incl. version scope), `cefr_evidence`,
  `ielts_evidence` (+ `is_ielts` VIEW over approved rows —
  derived-only by construction, INSERT into the view raises),
  `quarantine_record` (own technical id + kind CHECK),
  `mapping_provenance` (closed classification set). FKs enforced
  (`PRAGMA foreign_keys = ON`).
- New tests `evaluation/test_evidence_schema.py`: 10 passed on
  in-memory SQLite (structure, idempotent create, enum/FK/
  classification enforcement, view derivability + unapproved
  exclusion + view non-writability, many-topics-one-identity,
  quarantine/identity ID separation, snapshot immutability).
- No repo database touched (all `:memory:`). No CEFR
  canonicalization ran; no staging row admitted. Carried notes
  (updated post-resolution wording): BT-01 decision resolved —
  canonical CEFR assignment remains BLOCKED pending exact EVP
  release/version + license acquisition; BT-02 investigation
  resolved — 8,027-row vintage remains UNLOCATED and all affected
  staging rows remain quarantined.

- [ ] Schemas hold every locked field; quarantine ID ≠ identity ID
- [ ] Provenance append-only; snapshot identity immutable
- [ ] `is_ielts` has no independent write path (projection or
  recomputed cache only)
- [ ] BLOCKED notes carried: no canonical CEFR values (BT-01
  open); no 8,027 rows admitted (BT-02 open)
