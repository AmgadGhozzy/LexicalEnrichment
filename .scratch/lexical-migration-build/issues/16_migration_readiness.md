# 16: Migration Readiness Decision (348 evidence gates G1–G4)

**Status:** CLOSED (READY — ELIGIBLE, NOT WRITTEN; NOT EXECUTED)
**Triage:** ready-for-human
**Decision owner:** human reviewer (user). Execution blocked by
governance lock (content-QA gate); this ticket asserts READINESS of the
4 gates and PROVEN rollback on a staging copy, not authorization to
write canonical.

**Decisions recorded (2026-09-08):**
1. 348 blind eval = ACCEPT (Strong Promotion Candidate). No amendment,
   no re-run, no stop-of-promotion.
2. Migration Decision = OPEN, opened under exactly the 4 pre-registered
   gates below. Canonical writes remain 0.

**Official state:**
- 348 = Strong Promotion Candidate
- Migration Decision = OPEN — ELIGIBLE, NOT WRITTEN
- Canonical writes = 0
- Governance lock = unchanged

Evidence artifacts (all read-only produced; 0 canonical writes):
- `output/migration_readiness/migration_manifest_348.json` (per-card,
  per-field lineage + G3 action; sha256 `a053dba7…13fa`)
- `output/migration_readiness/migration_policy_summary.json`
- `output/migration_readiness/manifest.json`

---

## G1 — Identity safety: PASS (1 open flag)

- 356 candidate keys vs `WordsMaster.db` `wordsMaster` (7300 rows):
  **356/356 exact 1:1 match on (wordEn,pos)**, 0 missing, 0 multi,
  0 pos-variant. No new lemma/pos introduced; candidate identity dict
  preserves `lemma`/`pos` verbatim.
- `id` = stable identity, `rank` = derived ordinal: NEITHER is in the
  candidate schema (`identity` carries only lemma/pos/cefr). No
  id/rank recomputation anywhere in the manifest.
- Open flag: CEFR drift on 3 cards where candidate `identity.cefr`
  != legacy `cefrLevel`: `deal/verb` A2→B1, `double/pron` A2→B1,
  `spell/verb` A1→C1. CEFR is a value field (legacy provenance
  unknown per field rules) → NOT auto-promoted; flagged for manual
  verification before any write on those 3.

## G2 — Evidence/provenance safety: PASS (1 open item)

- Lineage object exists per card per field in
  `migration_manifest_348.json`:
  legacy seed (`WordsMaster.id`) → candidate raw
  (`generated_356/raw/<lemma>__<pos>.json`) → validator
  (`artifact_pass` + per-field validator status) → decision provenance
  (`field_decisions.{action,evidence,reason}` + `source_type`) →
  adjudication verdict (frozen `ai_judge_seeded348/decode_analysis`) →
  G3 action.
- Input hashes recorded in manifest: eval_input
  `86b3ea701153370130172c74a9147e6f65b54d2773652f79f3596e7177512545`,
  decode_analysis `7485e017144da283b6bf13f10b109b880dd55f3b3dd60a6d71db86f2d9aa493a`,
  batch_merge request hashes `c72019e2…` / `23f7e331…`,
  seed_snapshot_sha256 `197089b3…7f3`, prompt sha256 `fdb8716e…`.
- Provenance gaps: the 8 batch-decision 429-fail cards
  (bare/adj, flame, ice cream/noun, line-up/verb, oral/adj, over/prep,
  refuse/verb, trace/verb) are ABSENT from the 348 eval → outside
  migration scope by construction.
- Open item: `billion/num` is IN the eval but its decision provenance
  was never persisted (single line shows `decisions_status:
  error: 429 RESOURCE_EXHAUSTED`; the retry did not write a decision
  line). Execution exclusion: billion must NOT be promoted until its
  decision provenance is reconstructed from batch job B outputs
  (requests_b_input hash above), or — default safe path — keep all
  billion fields as legacy in this wave.

## G3 — Field-level promotion policy: PASS (codified)

Policy v1 (embedded in `export_migration_manifest.py` + manifest):
- PROMOTE a field iff adjudication verdict == `candidate` AND the
  candidate value is non-empty. Otherwise KEEP (legacy/tie/cannot →
  keep; never downgrade on a non-candidate verdict; never auto-fill an
  empty candidate value: validity > inventory; no force-fill of null
  mnemonic).
- `sense_separation` is NEVER auto-promoted (manual band — both AI
  abstention and human mutual-conservatism on the sample; no promotion
  merely for extra detail).
- CEFR / difficultyScore / unitId / rank / id: NOT in promotion scope.
- Human layer (30-sample) corroboration: definition 5–0, arabic 9–1,
  mnemonic 2–0, translations 0 human legacy-wins, relations legacy
  criticals ×5 human-side, examples 24–6 candidate; 0.6952 agreement
  is on-perceptual-reference, not a confounder of the promotion rule.

Adoption counts (348 cards):
| field | promote | keep | manual |
|---|---|---|---|
| definition_en | 50 | 298 | – |
| explanation_ar | 77 | 271 | – |
| examples | 163 | 185 | – |
| translations | 169 | 179 | – |
| mnemonic | 23 | 325 | (2 candidate-wins had empty value → kept) |
| relations.synonyms | 328 | 20 | – |
| relations.antonyms | 232 | 116 | – |
| relations.collocations | 345 | 3 | – |
| sense_separation | – | – | 348 |

Guards exercised: mnemonic 2 empty-kept; relations.antonyms 110
empty-kept (no inventory loss by overwriting valid legacy with
absence). All 23 legacy `invalid_relation_synonym` critical cards →
relations promoted (synonyms+collocations 23/23; 6 antonyms kept by
the empty-guard).

## G4 — Write strategy: PASS (plan; execution remains gated)

Ready-to-execute design (NOT executed, canonical writes still 0):
1. **Backup first, always:** snapshot `WordsMaster.db` → `WordsMaster_backup_<run_id>.db`
   (dicPyImp `*_backup_*.db` convention). Never write in place.
2. **Additive/versioned, single transaction:** one SQLite transaction
   across the promotion set; each UPDATE keyed by stable primary key
   `id` (never recomputed), touching only the PROMOTED columns per the
   G3 table (candidate → legacy column map: definition_en→definitionEn,
   explanation_ar→definitionAr, examples→examples,
   translations(list)→arabicAr, relations.*→synonyms/antonyms/
   collocations, mnemonic→mnemonicAr; senses/semantic_tags manual).
3. **Audit trail:** per-field provenance rows written to a
   `field_versions`-style audit (value_before, value_after, source,
   decision, adjudication_ref, manifest sha256) so every promoted value
   is traceable; the manifest JSON is the durable lineage artifact.
4. **Rollback:** (a) transaction abort leaves DB untouched; (b) audit
   replay of `value_before` per field; (c) full backup restore as last
   resort. Idempotent by `id`+field.
5. **Staging dry-run first:** apply to a copy (existing
   `data/staging/LexicalStaging.db` path), then run
   `qa/verify_staging_integrity.py [run_id]` + validator enum contracts
   (`test_validator_characterization.py`) + JSON↔SQLite parity before
   anything else. No network.
6. Execution is NOT authorized by this ticket: governance content-QA
   gate must pass first; this ticket only certifies readiness.

## Open items (must close before execution, none blocks the verdict)
- G2: reconstruct billion/num decision provenance from batch job B (or
  keep billion legacy — excluded from this wave).
- G1: manual CEFR verify on deal/verb, double/pron, spell/verb.
- G4: full staging dry-run + rollback test to be run when unblocked.

## References
- Ticket 15 (seeded challenger): eval readout + human30 + reconcile.
- `evaluation/export_migration_manifest.py`: G2/G3 exporter (pure
  analysis; DB read-only).
- Inputs: `output/eval_seeded348_v1/*`, `output/ai_judge_seeded348/*`,
  `output/EXP-SEEDED-001A/generated_356/*`.

## Final ruling (user, 2026-09-08): closed as READY, NOT EXECUTED

Decision ratified verbatim in substance:

- G1: PASS — 3 CEFR flags do NOT block promotion; deal/verb,
  double/pron, spell/verb stay manual-review / no-write.
- G2: PASS — billion/num decision provenance missing → BLOCKED from
  promotion or stays legacy.
- G3: PASS — promotion independent per field per candidate verdict;
  empty / KEEP cells are NEVER touched; 345/348 relations DOES NOT mean
  "write all candidate relations" — policy is validity over inventory
  (established by the human layer).
- G4: PASS — plan only; NO execution before dry-run + rollback
  verification + governance-lock lift.

Promotion scope ratified (current eligible): Definition 50 · Arabic 77
· Examples 163 · Translations 169 · Relations subfield writes
(synonyms 328 / antonyms 232 / collocations 345) · Mnemonic 23 ·
Sense manual (never automated) · billion/num blocked. 348 are a
FIELD-LEVEL promotion candidate, NOT a bulk overwrite.

Operational sequence mandated BEFORE any canonical write:
G1/G2 blockers → staging dry-run → backup → transactional field-level
write → field_versions audit → integrity verification →
commit/rollback decision.

Abort doctrine (user): any failure in provenance, identity, or
rollback capability = ABORT — no "commit now, patch later". Humans
invented rollback because they cannot predict everything.

Invariant: canonical writes = 0 until the governance lock is lifted
EXPLICITLY.

## G4 dry-run executed on staging copy — rollback PROVEN

Tool: `evaluation/migrate_field_level.py` (`--dry-run`): copies
`WordsMaster.db` (sqlite backup API) to a sandbox under
`output/migration_readiness/dryrun/`, applies the G3 promotion cells in
a single transaction keyed by stable `id` (never row-overwrite, never
touching non-promoted columns), writes `migration_audit_2026_001`
(row-per-cell value_before/after + sha + provenance refs), verifies,
then ROLLS BACK by replaying `value_before` and drops the audit table.

Evidence (dryrun_report.json, 2026-09-08):
- promotion cells loaded/applied: 1384 (1387 per G3 minus 3 for
  billion/num exclusion)
- audit rows: 1384 == applied
- pre logical-state sha256: `56a5a095…81f02`
- post-apply sha256: `8d551000…c508d` (state DID change as intended;
  integrity_check ok; wordsMaster row count and id set unchanged)
- post-rollback sha256: `56a5a095…81f02` == PRE (rollback_restores_state
  = true)
- JSON cells written (examples, synonyms/antonyms/collocations) re-parsed
  successfully; non-promoted columns untouched by construction (proven
  by the full-state hash equality after rollback).
- canonical writes: 0. Production target refused by the tool itself
  unless --allow-production (never passed).

Conclusion: G4 write strategy is VERIFIED on a staging copy. The
pre-write checklist for a future canonical execution is:
G2 billion resolution → G1 CEFR manual verify → fresh backup
(`WordsMaster_backup_<ts>.db`) → transactional field-level apply →
audit → `qa/verify_staging_integrity` (on the staged copy's system-A
equivalent) → commit/rollback decision → then commit ONLY if every
verification passes. Abort otherwise. Governance lock remains the
external precondition.

## Comments

(append operator notes below this line; newest at the end)