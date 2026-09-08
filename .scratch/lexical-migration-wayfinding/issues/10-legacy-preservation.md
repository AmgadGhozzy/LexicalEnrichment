Type: grilling
Status: resolved

## Question

Which legacy fields are preserved indefinitely versus archived (legacy difficulty, legacy examples, legacy rank, original enrichment, original provenance) — and how is snapshot identity (on-disk 7,300 vs staging's 8,027-source) recorded so migration stays reversible/auditable?

## Evidence

- `forensic_report.md` §2 (HIGH flag): on-disk WordsMaster is not staging's source DB; resolve snapshot mismatch before any migration.
- `DECISION_LOG.md` (root): WordsMaster 7,300 import immutable; blind regeneration of trusted metadata rejected (wastes cost, breaks lineage).
- Draft rule to ratify: preserve legacy values as historical/source columns; never destroy provenance; migration reversible/auditable.

## Gate

BLOCKING — resolved. Reversibility/auditability section unblocked. Live carried-forward precondition: the 7,300 vs 8,027 source-vintage mismatch.

## Answer

Ticket 10 consolidates the already-locked decisions from Tickets 01, 06, 07, and 08 and does not reopen their field-level decisions.

1. Legacy preservation

The following legacy information MUST remain recoverable as historical/source evidence:

- legacy rank/frequency values — governed by Ticket 01
- legacy DifficultyScore — governed by Ticket 06 as LEGACY ONLY
- legacy example cells — governed by Ticket 07; all 43,800 cells preserved unchanged
- legacy CEFR values — governed by Ticket 08 as historical evidence with no automatic authority
- legacy definitionEn/definitionAr
- legacy IPA and phonetic fields
- legacy Arabic/translations
- legacy synonyms/antonyms/collocations/related-word/word-family content
- legacy usage notes
- legacy category/POS values where retained as source evidence
- legacy curriculum/unit associations

Preservation means the original snapshot remains recoverable and auditable. It does not require every legacy field to remain an operational canonical field indefinitely; active-schema versus archive placement is a later physical-design decision.

2. Legacy enrichment handling

Legacy enrichment content follows field-level QA:

- KEEP when evidence supports quality.
- REPAIR only when a deterministic, bounded defect is identified.
- REGENERATE only when an explicit field-level QA decision justifies replacement.
- Never perform blind mass regeneration.

Known deterministic contamination MUST be removed from learner-facing canonical content, including the identified grounding artifacts in `homemade.definitionAr` and `migrate.usageNote`.

CI/validation MUST reject URLs, grounding markers, and equivalent citation artifacts in learner-facing content fields.

3. Snapshot identity and provenance

Every imported legacy record MUST be traceable to its source snapshot through provenance containing, at minimum:

- source name
- source/version identifier where available
- source snapshot hash
- source row identifier
- import timestamp
- import/migration operation identifier where applicable

Snapshot identity is immutable. Provenance is append-only and MUST NOT be silently overwritten during migration.

4. Canonical legacy baseline

The on-disk 7,300-row `WordsMaster.db` snapshot is the canonical legacy baseline for migration analysis:

SHA256:
cfabafa8153521b3ebfe457f298f7e311cea25a2bbecb991a6e986fde286984f

It remains frozen and must not be modified as part of the migration work.

The 8,027-row staging source is recorded as a distinct source vintage because its provenance claims `WordsMaster.db` while its content does not match the frozen 7,300-row snapshot.

The 8,027-source vintage MUST be identified/reconciled before migration. Ticket 10 records this as a migration precondition; it does not resolve the vintage in this ticket.

5. Reversibility mechanics

Migration MUST be additive and reversible:

- new canonical structures are written alongside legacy structures;
- legacy data is never overwritten in place;
- no destructive transformation is permitted as part of the migration;
- a verified backup (for example `*_backup_<timestamp>.db`) is required before any database mutation;
- provenance and source snapshots remain recoverable after each migration stage.

A migration stage is auditable only if its inputs, outputs, provenance, and operation identity can be reconstructed without relying on mutable application state.

6. Evidence hierarchy

Ticket 10 does not promote legacy values to canonical authority.

The previously locked rules remain authoritative:
- Ticket 01 governs canonical frequency.
- Ticket 06 governs legacy DifficultyScore status.
- Ticket 07 governs canonical examples.
- Ticket 12 (when resolved) governs curriculum placement — legacy
  curriculum/unit associations remain source evidence only.
- Ticket 08 governs CEFR authority.

Legacy values remain available for forensic comparison, historical traceability, and QA unless a later explicitly approved archival policy changes their physical storage location without destroying recoverability.

Gate: RESOLVED / BLOCKING
