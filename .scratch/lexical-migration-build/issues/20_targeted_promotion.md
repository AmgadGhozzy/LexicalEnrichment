# Ticket 20 — Targeted Promotion (564 verified cells)

**Status:** CLOSED — EXECUTED / VERIFIED (human-owner verdict 2026-09-09; no reopen)
**Baseline:** Baseline-PostMigration-001 (canonical writes since baseline: 1 wave = 1,384 cells)
**Parent evidence:** Ticket 19 execution (`output/EXP-SEEDED-609/remediation_audit_609.json`) — the sole source of verdicts/candidates.

## Governance decision (human-owner, 2026-09-09): APPROVED — TARGETED PROMOTION
Not "promote all candidate wins". Promotion-eligible scope as ruled, then
CORRECTED (see Correction section — the as-written 555 was cell-unexecutable):
- examples: candidate wins with zero candidate-criticals → promotable. Tie /
  legacy / no-candidate / malformed → KEEP (legacy or MANUAL queue, no retry).
- relations: candidate wins passing the no-op guard → promotable (changed cells
  only). Byte-identical no-ops → DO NOT WRITE, excluded from counts.
- proclaim/noun: legacy-verdict cell (one of the 4 legacy wins); its 3
  candidate-critical findings subtract NOTHING from the winning population
  (aggregation error in the draft, not a finding against the winners).
- Validator failures are never auto-retried (contain-target precedent stands).

## Correction (human-owner approved 2026-09-09): 564, not 555
Cell-level evidence audit proved two aggregation slips in the draft arithmetic:
(1) proclaim double-count (legacy-win AND critical-reject); (2) relations counted
as 6 CARDS not 12 CELLS (all 6 synonym cleanups change, each removing exactly
the judge-flagged invalid item: that/this/defeat/merger; plus takeover antonyms).
Reconciled: 557 examples + 7 relations = 564 promotable;
564 + 22 tie + 4 legacy + 13 no-candidate + 1 no-ballot + 5 no-ops = 609 exact.
- Examples promotable: 557 (zero candidate-criticals among wins — verified).
- Relations promotable: 7 (6 synonyms + takeover antonyms; verified changed).
- No-ops (pre-marked, excluded): 5 antonym cells (this/det, that/pron, this/noun,
  that/det, conquest/noun) — judge tie-leniency on identical lists; they appear
  in audit as NO-OP / 0 bytes changed / not counted.
- Storage note (new shape, by design): remediated examples are stored as a
  compact-JSON array of exactly 3 strings (legacy 6-band object → baseline-3);
  relations stored as compact-JSON arrays (wave-1 convention). Future triage
  already parses both shapes (C1 array branch).

## Execution safeguards (locked, 12)
1. candidate provenance exists for every promoted cell.
2. candidate hash matches the evaluated artifact (recomputed from raw file).
3. verdict == candidate (decode join).
4. no candidate-critical error on the cell.
5. candidate non-empty + schema-valid (validator-pass re-asserted).
6. identity/protected fields untouched (cols ⊆ {examples, synonyms, antonyms}).
7. candidate_value == current_value → NO-OP pre-promotion (never a promotion).
8. the 5 no-ops excluded from promotion count (audited as NO-OP).
9. dry-run predicts exactly 564 changed cells (+ rollback equality).
10. backup-first + single transaction (verify-inside-txn, COMMIT only if clean).
11. field-level audit per cell (new table `migration_audit_2026_002`; wave-1 table
    untouched): id, field, value_before, value_after, hashes, candidate_hash,
    verdict, provenance.
12. post-write integrity + hash verification; canonical writes == 564 iff every
    check reconciles, else ABORT + rollback.
Forbidden: any write outside the 564; retries; regeneration; prompt/model/config
changes; scope expansion. After execution: STOP for the post-promotion evidence
report. No auto Ticket 21.

## Completion record (operator, 2026-09-09) — STOPPED, no transition
- Manifest `promotion_manifest_564.json` (sha `63cfac0a…`; 564 promos + 45
  excluded with reasons). Pre-write checklist: 564==564, cols {examples,
  synonyms, antonyms} only, 0 exception ids, 7300 rows, 0 before-drift,
  0 candidate-hash mismatch, 0 no-op leaks.
- Dry-run: applied 564, byte-diff EXACTLY the promo set, rollback equal.
- Backup `WordsMaster_backup_20260909T164125Z.db`; single txn verify-then-commit.
- Post-write (independent read-only re-verify): rows 7300, ids 1–7300 intact,
  integrity ok, audit_002 564 rows, audit_001 still 1384, pre `9c50a5b9…` →
  post `29850877…`. All 12 exception ids byte-identical (incl. billion).
  conquest syn promoted (defeat out, takeover in) / ant untouched WITH legacy
  spacing (no-op honored to the byte); takeover ant promoted (merger out);
  apology untouched (no ballot).
- Canonical writes this wave: 564 (557 examples + 7 relations). Total since
  baseline: 1,384 + 564 = 1,948 cells over 2 waves, 0 outside scope.

- 2026-09-09: Ticket created at decision time (decision arrived before the file).
  Correction + authorization recorded above before any execution. Operator
  proceeds: promotion manifest → dry-run(564) → backup → single-txn execute →
  post-verify → report → STOP.

## Post-closure evidence (operator, read-only, 2026-09-09) — NO NEW WAVE
- Baseline-002 FROZEN (`output/migration_readiness/baseline/Baseline-PostMigration-002.json`):
  logical `29850877…` (= wave-2 post), rows 7300, identities 7300, audit_001 1384
  + audit_002 564 (hashes recorded), schema delta vs 001 = +audit_002 table only.
- Protected-column drift vs wave-1 PRE-migration backup (29 cols incl. id/lemma/
  pos/rank/frequency/CEFR/difficulty/unitId/phonetics, all 7,300 rows): 0 drifted.
  Neither wave touched protected ground — proven, not asserted.
- Deterministic regression, full 7,300, frozen triage path
  (`output/triage/regression_post20/triage_rerun_7300.json`, sha `cdf4e458…`,
  65,700 records, NO quota breach): relations flags 0/3 subfields (7 promoted now
  KEEP; 5 no-op antonyms healed via overlap removal when synonyms were cleaned);
  examples flags 40 = EXACTLY the adjudicated remainder (22 tie + 4 legacy-win +
  13 no-candidate + 1 no-ballot), 0 new. Promoted 557/557 examples verified KEEP
  by the same rules that flagged them. proclaim/noun re-surfaces (legacy kept by
  verdict) — known-adjudicated, not new.
- Remaining queues, REVIEW-ONLY (membership exact; several are correct
  abstentions, none auto-converted to work): sense 7,300 + 24 presets (MANUAL
  policy); 13 no-candidate (10 syllables-null monosyllabic + up-to-date/
  decision-making/yes contain-target — frozen-gate stands); 1 malformed ballot
  (apology/noun — re-judge is a methodology decision, not taken); 4
  legacy-preferred (leave/duck/cathedral/proclaim — judge-verified legacy
  superiority); 22 ties (judge-verified parity); 5 no-ops (correct skips);
  8 billion BLOCK (provenance gap stands).
- State: migration COMPLETE FOR APPROVED WAVES (1,948 cells / 2 waves / 0
  out-of-scope). Generation/promotion lock: ON.

## Comments

(append operator notes below this line; newest at the end)
