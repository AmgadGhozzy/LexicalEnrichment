# 02: Gate B — 8,027 vintage reconciliation + 692 gap (BT-02)

**What to build:** the closed Gate B investigation — the 8,027-source
vintage identified (what it is, where it stands relative to the frozen
7,300 snapshot) with an explicit ruling on how its rows (incl. the
727) may ever enter any migration path, plus reconciliation of the
692-vs-695 arithmetic gap. Until then the quarantine-only rule stands.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Spec ref:** spec §3 (727/vintage, OPEN gap item) + §6 (snapshot
identity, Gate B); wayfinding 10 (precondition, additive mechanics).

## Investigation record (read-only; zero DB opens, zero writes)

Method: disk inventory (`**/*.db`, `**/*backup*`) + full reads of
`forensic_report.json` and `forensic_727.json` (439 lines). No
database was opened; no forensic was re-run.

1. Vintage identity — UNLOCATED (valid negative finding).
   - On disk: exactly three databases — `WordsMaster.db` (7,300
     rows, 2026-03-02, `cfabafa8…86984f`), `LexicalStaging.db`
     (8,027 rows, 2026-09-03, `8f1a382d…add060`),
     `IeltsWord.db`. No backups, no second WordsMaster anywhere.
   - Staging `source_records` claim `source_db=WordsMaster.db`
     with `source_row_id` up to 8,027 plus a different
     serialization vintage (array-encoded fields, truncated
     phonetics, null Ar/sense/mnemonic). Therefore staging was
     built from a post-March WordsMaster revision (≥8,027 rows)
     that is not present on disk and cannot be fingerprinted
     further from available evidence.
   - Entry rule: CONTINUED QUARANTINE. Identification of the
     vintage is not an admission decision: even were the export
     located, the 727 remain quarantined pending per-item review.

2. 692-vs-695 gap — RECONCILED as draft-prose error (no data
   discrepancy, no value invented).
   - Artifact closes exactly: 121 + 571 + 32 + 3 = 727.
   - Draft prose never closes: 695 + 32 + 3 = 730 ≠ 727, so
     "695 exact duplicates" has no consistent reading.
   - Arithmetic observation: 121 + 571 = 692, and 692 + 3 = 695
     exactly — i.e. the draft figure equals the main block plus
     the 3 brand-new lemmas double-counted into the "duplicate"
     bucket, while mislabeling questionable-POS expansions as
     "exact duplicates". The "695" is therefore struck from the
     record; 121+571+32+3 stands unconditionally. The gap item
     is closed (explained), not carried.

Gate B state: investigation resolved; MIGRATION PRECONDITION
PERSISTS — no staging-sourced row enters any migration path until
the vintage is located or its rows are individually adjudicated.

- [ ] 8,027 vintage identified and documented with evidence
- [ ] Entry rule for vintage rows stated (or continued quarantine)
- [ ] 692-vs-695 gap reconciled against the artifact (no invented values)
- [ ] Reconciliation establishes provenance/matching ONLY — resolving
  the gap does not authorize promotion of any of the 727 rows to
  canonical data; quarantine stands until per-item review says otherwise
- [ ] 121+571+32+3 authority status confirmed or explicitly superseded
- [ ] No staging row promoted to canonical data by this ticket
