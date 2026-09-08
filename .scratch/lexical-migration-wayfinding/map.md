## Destination

A closed decision map over the 12 open migration questions — each resolved to a recorded decision with evidence pointers and a BLOCKING / NON-BLOCKING / DEFERRED gate tag — sufficient to write a buildable implementation spec via `/to-spec`. Zero DB mutation; Golden Set, 7,300-row WordsMaster baseline, and all `evaluation/forensic_audit/` artifacts intact.

## Notes

- Domain: LexicalEnrichment, two systems (System A `pipeline/` sleeping; System B `evaluation/` active). Shared vocabulary only via `evaluation/utils.py` + `evaluation/lexical_validator.py`. Do not cross-import.
- Vocabulary discipline (`domain-modeling`): keep **lexical identity vs frequency vs curriculum vs CEFR evidence vs IELTS evidence vs LLM enrichment vs word relations** separate in every ticket. Never collapse them into one field.
- Standing preferences: evidence > assumption; NULL semantics preserved (`phonetic_uk=null` means "same as US"); provenance never overwritten; `id != rank != curriculum_position`.
- Existing artifacts are **ready evidence, not new tickets**: `forensic_727.json`, `forensic_difficulty_v2.json`, `legacy_examples_*_sample100.json`, `ielts_mapping.json` (explicitly a *review artifact, NOT a migration*), `forensic_report.md` + `.json`, root `DECISION_LOG.md` (current; no second copy).
- RULING (review-approved): `forensic_727.json` decomposition 121 + 571 + 32 + 3 is authoritative until the underlying artifact is explicitly reconciled. The draft plan's "695 exact duplicates" is not used. Note the open arithmetic gap: 121 + 571 = 692, not 695 (diff 3, unexplained — no guessing; tickets 02/05 carry it as an explicit open item). No recount of the 727, no DB touch.
- Known snapshot flag (`forensic_report.md` §2): on-disk `WordsMaster.db` (7,300 rows) is NOT the DB staging was imported from (`source_row_id` up to 8,027). Snapshot-identity resolution is a precondition to any migration and is referenced in tickets 02 and 10 — it is not itself a 13th ticket.
- Governance lock for the whole effort: NO migration, NO 8K run, NO schema comparison, NO LEX-001→LEX-021 implementation backlog, NO re-running forensics, NO Golden Set modification.
- All 12 tickets are `grilling` (HITL): each resolves through live exchange with the human, one ticket per session. No AFK execution inside the map.

## Decisions so far

- [Frequency source](issues/01-frequency-source.md): wordfreq Zipf canonical, closing the AGENTS.md vs DECISION_LOG.md contradiction; per-observation provenance (source/version/lang/metric/observed_at, corpus identity kept separate from package version); dense rank by descending Zipf, alpha lemma display-only; legacy rank/frequency 1–6 preserved, never consumed; new identities get stable IDs, never renumbered.

- [Identity normalization](issues/02-identity-normalization.md): key `(normalized_lemma, canonical_pos)`; deterministic folding (trim/lowercase/NFC/single-space, diacritics preserved); hyphen-without-space = single-word, whitespace = multiword → 04; possessives map to base; lemma-only identities; zero-derivation legitimacy delegated to 03; names/brands excluded.
- [POS mapping](issues/03-pos-mapping.md): 11-tag enum locked per `lexical_output.v1.json` (identical in v1.1-candidate); one POS per identity, composites rejected as stored values; IELTS 4 tags map 1:1, other 7 never inferred from IELTS; zero-derivation per-item HITL; closed-class→open-class mismatches presumptively malformed (rebuttable per-item, never blanket rejection).
- [CEFR precedence](issues/08-cefr-precedence.md): curriculum/difficulty barred as CEFR inputs; LLM CEFR evidence-only; legacy CEFR = preserved evidence, no auto-authority (unknown provenance); canonical CEFR only via explicit versioned precedence policy; external lexicon selection is an explicit follow-up; versioned history, no destructive overwrite.
- [Difficulty decision](issues/06-difficulty-decision.md): LEGACY ONLY — KEEP rejected (row-order rank + unknown CEFR + 29% clamp-tautology + mixed processes), REMOVE rejected (preserved, 0 out-of-bounds so no repair due); staging recompute rejected outright (unknown computation); future redesign gated on real frequency rank + documented weights + proven signal beyond CEFR+frequency.
- [Example contract](issues/07-example-contract.md): 3 per identity default, 4th/5th for genuine polysemy only (sense-driven, auditable); exact normalized-lemma token, no exceptions; sense/POS fit + naturalness + no leakage; word-count never certifies CEFR; full regeneration, legacy 43,800 preserved; structural pass ≠ quality, human gate required.
- [Multiword policy](issues/04-multiword-policy.md): MULTIWORD_QUARANTINE adopted (02-block satisfied); whitespace = atomic quarantined expression, never split, never minted as identity; quarantine ID ≠ lexical-identity ID; 34 IELTS multiwords keep topics; DDL deferred to spec. RESOLVED / NON-BLOCKING.
- [IELTS matching](issues/05-ielts-matching.md): 1–6 cascade locked, classification ≠ identity creation, matching only against the 02/03 universe; baseline 678/34/276/34/0 = 1,022 ratified (712 overlap, 310 unrepresented) with deterministic spec-stage recompute clause; duplicates stay separate rows; IELTS evidence-only, never overwrites; 276 = gated pool; #2-vs-#3 distinction is a spec verification item.
- [is_ielts placement](issues/09-is-ielts-placement.md): evidence table sole truth, flag derived-only (no independent write path), strictly boolean (1 iff ≥1 approved row); stale cache = defect, never second truth; storage deferred to spec. RESOLVED / NON-BLOCKING.
- [Legacy preservation](issues/10-legacy-preservation.md): consolidates 01/06/07/08 by reference (no re-litigation); enrichment KEEP/REPAIR/REGENERATE via field QA + deterministic leak removal + CI guard; snapshot provenance contract; 7,300 baseline frozen; 8,027 vintage = unresolved precondition; additive/reversible mechanics with mandatory backup; preservation ≠ production-schema museum.
- [Curriculum placement](issues/12-curriculum-placement.md): gates first (02/03) then mint ID → provenance → frequency → CEFR → IELTS → curriculum last; IDs never renumbered; unitId pedagogical bucket, never derived; 276-pool only, mapping creates nothing; legacy units re-bucketable. RESOLVED / NON-BLOCKING.
- [LLM versioning schema](issues/11-llm-versioning-schema.md): physical DDL deferred, 7-dimension provenance minimum locked (prompt/schema/model/generation-config/reasoning-grounding/run-provenance incl. input hash/integrity, append-only); to-spec anti-forgetting clause bound; v2.2.3 held as candidate, no sweeps. RESOLVED / DEFERRED.

## Not yet specified

- Exact 1,000-pilot stratification dimensions and seed policy — graduates after tickets 01 (frequency source) and 08 (CEFR precedence) resolve.
- Deterministic repair list scope (IPA fallback, grounding-artifact removal, schema normalization) — graduates after ticket 10 (legacy preservation) resolves.
- Quarantine-table DDL shape for the 727 — graduates after tickets 02 (identity) and 05 (IELTS matching) resolve; quarantine holds, never migrates, until then.

## Out of scope

- LEX-001→LEX-021 as an implementation backlog — the 21 tickets are draft thinking only, never published to the tracker.
- 8K run, production migration, schema/model-matrix comparison — locked until the content-QA gate passes (`AGENTS.md` governance).
- Golden Set modification (`golden_set/golden_v2.json`, 160 entries) — immutable holdout.
- Migrating the 727 into canonical identity; using IELTS as CEFR/frequency truth; LLM-regenerated IPA; manufactured syllabification; sentence-length-as-CEFR; treating structural validation as semantic quality.
