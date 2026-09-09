# Ticket 21 — Derived Layer Build

**Status:** APPROVED — Derived Layer v1.1 APP-READY · CANONICAL-SAFE · GOVERNANCE-CLOSED (owner final sign-off 2026-09-09; all gates green; canonical lock ON)
**Baseline:** Baseline-PostMigration-002 (canonical frozen; zero canonical writes under this ticket)
**Parent:** Rapid Audit findings (identity clean, id==rank conflation live, units.totalWords = distinct lemmas, 1 true near-dup, IELTS mapping 1,022 records).

## Authorized scope (verbatim decision)
1. Oxford / IELTS views (as views or separate materialized artifacts; NO copying
   of lexical records): Oxford3000, Oxford5000, IELTS, Oxford ∩ IELTS, IELTS-only,
   Oxford-only, CEFR × IELTS, CEFR × Oxford — keeping IELTS provenance tiers
   (exact lemma+POS / same lemma different POS / multiword).
2. Evidence layer: per lexical_identity → Oxford evidence, IELTS evidence, CEFR
   evidence, frequency observations (versioned sources; replaceable without
   touching the word).
3. Curriculum layer: CEFR ≠ level, unit ≠ CEFR, category ≠ unit,
   frequency ≠ difficulty. Same 7,300 words serve Oxford / IELTS / General /
   Academic / custom paths with no duplicate vocabulary and NO direct unit
   redistribution.
4. `units.totalWords`: NO column change. Document semantics
   (`totalWords` = distinct lemmas per unit); derived/app layer uses the
   explicit name `distinctLemmaCount`.
5. `no-one` / `no one`: MANUAL REVIEW track — NOT in derived-layer execution.
   No merge/delete/auto-CEFR. Later owner decision only (retain both /
   canonicalize + variants / retain + explicit equivalence; CEFR from provenance).
6. Add-word protocol (write now): identity sequence independent
   (`lexical_id ≠ frequency_rank ≠ curriculum_position`); pipeline normalize →
   dedupe → evidence → frequency observation → derived rank → CEFR evidence →
   enrichment → curriculum assignment → derived views. The 276 IELTS
   NEW_SINGLE_WORD stay CANDIDATE additions, never canonical words.

## Hard forbids (verbatim)
No WordsMaster.db modification; no ID renumbering; no canonical rank rebuild;
no direct unit redistribution; no auto-merge; no new LLM sweep; no 7,300
regeneration; no IELTS words into canonical; no Oxford/IELTS copies into
independent word tables.

## Implementation record (operator)
- Durable specs (repo `derived/`): `schema.sql` (evidence/curriculum/tracking
  DDL + totalWords semantics comments), `add_word_protocol.md` (explicitly
  requested).
- Execution 2026-09-09: builder `evaluation/build_derived_layer.py` (canonical
  hash asserted pre-read; 7 files); self-audit 14 checks PASS
  (`output/derived/audit.json`): manifest hashes verified, canonical bytes
  unchanged vs Baseline-002, evidence 7,300/7,300 ids 1–7300, oxford partition
  5,831+1,469, IELTS tiers consumed 678/34/34 → 686 matched identities,
  intersections reconcile (both 636 / ielts-only 50 / oxford-only 5,195 /
  neither 1,419), 136 units with distinctLemmaCount == canonical totalWords,
  curricula reference existing units only, ZERO enrichment payload copied.
  `no-one`/`no one` untouched (MANUAL track). No app consumption yet — owner
  reviews this audit first.
- 2026-09-09: FORENSIC REVIEW reconciliations (owner CONDITIONAL PASS —
  HOLD FOR 2, both closed by operator, sign-off is owner's):
  (1) HASH BLOCKER resolved WITHOUT touching any artifact: proven live
  three-way equality on FILE BYTES — `sha256sum WordsMaster.db` ==
  manifest.canonical_db_sha256 == Baseline-002.file_sha256 ==
  `66fcf8b9…e3eba7`. The remembered `29850877…` is the CONTENT-level logical
  hash (Baseline-002.final_logical_hash_wordsmaster) — different function,
  both pinned since wave-2; comparing them across was the entire confusion.
  Manifest now carries an explicit `hash_semantics` block stating this.
  Gate as demanded (bytes == manifest) PASSES exactly.
  (2) `views/ielts_unmapped.json` ADDED as ordered (34 multiword rows with
  source_row_id/source_text/topic/normalized_form/match_status; NOT members,
  no fake identities, NOT in matched counts). Builder updated for
  reproducibility; full rebuild re-verified: all 7 prior artifact hashes
  BYTE-IDENTICAL, audit re-run PASS, manifest self-consistent (9 files).
  Also added: `normalization_provenance` block in manifest (mapping
  produced_by BT-09 cascade + rule_order + derived join rule + builder).
  Curriculum field: `rule` already carries explicit ordering semantics
  (`…by ieltsCount desc, stable by unitOrder`) — no `recommended_learning_order`
  anywhere; no change made. API LexicalRepository noted as app-build work
  (no app exists yet; no code written).
  requested).
- Generated artifacts (`.scratch/.../output/derived/`, hash-manifested):
  `evidence_layer.jsonl` (7,300), `views/` (oxford + ielts + intersections),
  `curriculum/` (units_derived + computed curricula), `manifest.json`.
- Views carry REFERENCES (id/lemma/pos) + derived attributes ONLY — audited for
  zero enrichment payload.
- Naming honesty (operator finding, pre-build): repo holds NO Oxford
  3000/5000 source lists (glob-clean) and `fromOxford` is an unversioned binary
  flag covering 5,831 rows — it is NOT the Oxford 3000. Artifacts are therefore
  named `oxford_flagged` / `non_oxford` (not Oxford3000/5000); true
  3000/5000-named views await versioned source lists. Same for IELTS: tiers
  recorded exactly as the mapping classifies them.
- `no-one`/`no one` untouched (MANUAL track preserved).

## Comments

- 2026-09-09: Opened per Derived-Layer governance decision. Operator builds
  specs + artifacts + self-audit, then STOPS. App consumption only after the
  derived-layer audit in this ticket.

(append operator notes below this line; newest at the end)
