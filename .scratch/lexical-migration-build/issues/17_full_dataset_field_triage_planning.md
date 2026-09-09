# 17 — Full-Dataset Field Triage Planning

**Status:** CLOSED — DESIGN VALIDATED / RULES FROZEN — READ-ONLY (quotation micro-bug: KNOWN LIMITATION, not a failed gate)
**Opened:** 2026-09-08 (user decision: planning/design/tests ONLY — no execution ticket, no generation)
**Design review:** 2026-09-08 — DRAFT v0.1 APPROVED WITH 4 mandatory amendments (§§3–6 amended below; NO-OP guard §7 unchanged). Implementation + unit tests + sample ≤300 read-only AUTHORIZED. Full-7300 run still requires sample review → rule freeze → NEW governance decision → NEW execution ticket.
**Baseline:** `Baseline-PostMigration-001` (`output/migration_readiness/baseline/Baseline-PostMigration-001.json`)
**Parent context:** tickets 15 (348 verdict) + 16 (migration wave-1 EXECUTED, verification PASS)

## 1. Scope
- Population: 7,300 identities in `WordsMaster.db` table `wordsMaster` (post-migration state = baseline; canonical writes since baseline: 0).
- Triage unit: (identity × enrichment field). In-scope fields (triage vocabulary matches G3):
  `definition_en`, `explanation_ar`, `examples`, `translations`, `mnemonic`,
  `relations_synonyms`, `relations_antonyms`, `relations_collocations`,
  `sense_separation` (AMENDMENT 2: in-scope, default MANUAL_REVIEW, quota-exempt)
  (DB columns: `definitionEn`, `definitionAr`, `examples`, `arabicAr`, `mnemonicAr`,
  `synonyms`, `antonyms`, `collocations`; sense has no single column — record carries
  `primarySense` in evidence).
- Explicitly OUT of triage labeling: identity/protected columns
  (`id`, `wordEn`, `pos`, `rank`, `frequency*`, `cefrLevel`, `difficultyScore`,
  `unitId`, phonetics, `primarySense`, `category`, `register`, `semanticTags`, …)
  and the 12 exception-track cards (§8 — pre-set statuses, excluded from quotas).
- Frozen inputs (never re-opened here): approved seeded prompt/config, AI-judge rubric,
  348 verdicts, wave-1 manifest. Triage consumes the baseline; it does not re-judge it.

## 2. Decision taxonomy (per field — CLOSED set, no free text)
- `KEEP` — passes all deterministic checks. No LLM, no human.
- `DETERMINISTIC_REPAIR` — defect fixable by a rule with a byte-verifiable postcondition
  (re-serialization, whitespace normalization, structural guards). Repair scripts assert
  postcondition + record before/after hashes. LABEL ONLY in this ticket — any write is a
  future authorized execution.
- `LLM_REVIEW` — needs a seeded-candidate judgment under the approved FROZEN config
  (future execution wave, if authorized). Requires `defect_code` + `evidence`.
- `MANUAL_REVIEW` — human-owner queue (semantics, nuance, Arabic quality, CEFR-adjacent).
- `BLOCK` — do-not-touch until a named precondition clears (e.g. provenance gap à la
  `billion/num`; 429-failed cards with no decision record).
- Inventory rule (AMENDMENT 4): `NULL` ≠ `[]`, and NEITHER is itself a defect.
  Empty relation inventory is not a defect; defect must be in the validity of existing
  content, never in item count (Validity > Inventory, consistent with prior decision).
  `NULL` vs `[]` is recorded in `evidence` (distinguishing missing from cleaned-empty)
  with status KEEP and no defect code. (The "empty candidate ⇒ keep legacy" rule stays
  a future-promotion rule, NOT a triage rule.)

## 3. Triage rules (deterministic-first — v0.1 FROZEN with amendments)
R1. Staged exit: cheap deterministic checks run first; a field exits at the first
    decisive stage. The LLM never triages — it only appears downstream as a LABEL.
R2. Circuit breakers, not quality expectations (AMENDMENT 1): quotas bound the FLAGGED
    share (status != KEEP) produced by deterministic rules per field. If a quota
    breaks, the RULE is over-sensitive — HALT the run + review the rule. NEVER tune
    the quota to rescue the data (a tuned quota is administrative decor).
    Initial quotas: `examples` 35%, `relations_synonyms` / `relations_antonyms` /
    `relations_collocations` 30% each, `translations` 30%, `explanation_ar` 20%,
    `definition_en` 20%, `mnemonic` 20%. `sense_separation`: NO prevalence quota
    (default MANUAL_REVIEW by design — quota-exempt entirely).
R3. No open-ended LLM in the loop: triage is code + SQL over a read-only snapshot.
R3b. HARD_FAIL vs SOFT_SIGNAL (AMENDMENT 3, examples): structural checks
    (`contains_target` phrase-aware, JSON/band structure, duplicates, empty bands)
    are HARD_FAIL → deterministic defect. `grammar sanity` and `POS/sense
    consistency` heuristics are SOFT_SIGNALs → evidence only; they escalate to a
    queue ONLY when ≥2 INDEPENDENT soft signals combine on the same record
    (named constant `SOFT_ESCALATION_THRESHOLD=2`, reviewable at sample).
    A lone soft signal ⇒ KEEP with the signal recorded in `evidence.soft_signals`.
    Rationale: the AI-judge example-sense failures must not re-enter through the
    back door. Sentence-length → CEFR remains ABSOLUTELY FORBIDDEN.
R4. Exceptions (§8) are pre-set and quota-exempt; their outcomes NEVER alter triage policy.
R5. Determinism proof: versioned rules file (`triage_rules_v1.*`); manifest bytes stable
    across re-runs (sorted keys, fixed thresholds); manifest hash recorded per run.
R6. Mandatory pre-transaction NO-OP guard for ANY future promotion loader (§7) —
    designed here, enforced at execution.

## 4. Field-specific check families (v0.1 FROZEN with amendments)
- `examples` (AMENDMENT 3): HARD — exact-lemma token (`contains_target`, phrase-aware
  for multi-word/hyphenated lemmas), JSON/band structure (≥1 non-empty band),
  cross-band duplicates, empty bands. SOFT (evidence-only; escalate only on
  combination per R3b) — terminal-punctuation sanity, leading-capital sanity.
  POS/sense-consistency heuristics stay OUT of hard defects (back-door ban).
  FORBIDDEN: length-based CEFR inference (legacy anti-pattern, FinalClean).
- `relations_*` (AMENDMENT 4): HARD — JSON-array validity, self-reference, exact
  duplicates, non-string items, synonym∩antonym overlap. NOT defects: empty `[]`,
  `NULL` (recorded in `evidence` only). POS-validity of content is NOT
  deterministically decidable — documented gap, no heuristic substitute.
  Collocation-without-lemma: SOFT.
- `translations`: HARD — empty, duplicate slots (case-insensitive). SOFT — no-Arabic-script.
- `explanation_ar`: HARD — empty, generic-null, no-Arabic-script.
- `definition_en`: HARD — empty, generic-null, circular (`is_circular_definition` narrow patterns).
- `sense_separation` (AMENDMENT 2): IN-SCOPE triage field, DEFAULT `MANUAL_REVIEW`
  for every record (defect_code null, requires_human true, quota-exempt). No LLM, no
  deterministic semantic judgment. Enters record vocabulary + counts.
- `mnemonic`: NULL ⇒ KEEP (`evidence.null_valid`, quality human-gated); empty string or
  generic-null text ⇒ DETERMINISTIC_REPAIR (normalize-to-NULL proposal, label only);
  present non-generic text ⇒ KEEP (no usefulness auto-judgment).

## 5. Output artifact (schema v0.1 FROZEN with amendments)
`output/triage/triage_manifest_7300_v1.json`:
```json
{
  "manifest_id": "triage_manifest_7300_v1",
  "rules_version": "triage_rules_v1",
  "baseline": "Baseline-PostMigration-001",
  "baseline_hash": "<final logical hash from baseline file>",
  "records": [
    {"identity": {"id": 5030, "lemma": "abandon", "pos": "noun"},
     "field": "examples",
     "current_value_hash": "sha256:<of normalized current cell>",
     "triage_status": "LLM_REVIEW",
     "defect_code": "EX_NO_LEMMA_TOKEN",
     "evidence": {"failing_bands": ["B2"], "checked": "contains_target"},
     "requires_llm": true,
     "requires_human": false}
  ]
}
```
Record key: (`id`, `field`). `defect_code` namespaces: `EX_*`, `REL_*`, `TR_*`, `AR_*`,
`DEF_*`, `SENSE_*`, `MNE_*`. `KEEP` records carry `defect_code: null` + `evidence.checked`
(the checks passed). Manifest hash + per-status counts + quota report accompany the file.

## 6. Sampling / validation plan (v0.1 FROZEN with amendments)
- Engine = pure functions over a read-only baseline snapshot + unit tests on synthetic
  fixtures (each rule: pass-fixture + fail-fixture; tests live with the engine).
- Characterization run on a STRATIFIED SAMPLE (n=300 FIXED — design-validation ONLY,
  NOT a quality estimate of the 7,300): allocation proportional over CEFR×POS with
  floors for tiny strata; representation quotas: ≥15 multi-POS-lemma cards, ≥10
  technical-category cards (Numbers/Time/Math, Nature/Science, Health/Senses), ≥25
  wave-1 (348) cards; the 12 exception-track cards EXCLUDED (preset, quota-exempt).
  Deterministic seed `triage-sample-v1`; sample manifest saved for reproducibility.
  Function chain ONLY: rules → 300 stratified → distribution/quota behavior →
  human-owner spot check → rule freeze.
- Quota-gate: any field breaching its quota halts and sends the RULE back to design.
- Full-7,300 run is NOT part of this ticket: it awaits a NEW governance decision
  (even though read-only). This ticket covers design + unit tests + sample-scale
  validation runs (≤300 rows, read-only) ONLY.
- Governance-gate checklist to open triage-execution authorization: design approved,
  tests green, sample distribution reviewed, quotas sane, rules version frozen,
  artifact schema frozen.

## 7. Mandatory NO-OP guard (future waves — non-negotiable)
Provenance: wave-1 verification found 195 no-op writes (candidate bytes == legacy bytes;
judge tie-leniency on verbatim-preserved seeds; zero data impact, faithfully audited).
Guard cascade, enforced in the promotion loader BEFORE any transaction:
```
candidate_value == current_value
        ↓
NO-OP
        ↓
DO NOT WRITE
        ↓
DO NOT COUNT AS PROMOTION
```
No-ops are counted separately (`noop_documented`, as in wave-1: 195) and NEVER inside
promoted counts. Discovering post-hoc that "we wrote the same thing" is not a result —
the filter must make the write impossible.

## 8. Exceptions — separate review track (human-owner; does not shape policy)
Statuses frozen; triage engine MUST skip-or-preset these identities:
- `spell/verb` (id 3136, legacy A1; candidate C1) → MANUAL_REVIEW.
- `deal/verb` (id 551, legacy A2; candidate B1) → MANUAL_REVIEW.
- `double/pron` (id 1239, legacy A2; candidate B1) → MANUAL_REVIEW.
- `billion/num` (id 1789, legacy A2) → BLOCKED_G2 (no provenance/decision record;
  enters canonical promotion ONLY after provenance rebuild, else stays legacy).
- 8 legacy-only (seeded-gen 429 fails, no decision record → KEEP, no auto-regeneration):
  `bare/adj` 4004, `flame/noun` 4499, `ice cream/noun` 2734, `line-up/verb` 412,
  `oral/adj` 3628, `over/prep` 83, `refuse/verb` 3043, `trace/verb` 3916.
Evidence: `output/migration_readiness/verification/exceptions_evidence.json`.
All 12 legacy values verified intact post-migration. NO exception may change §§2–6.

## 9. Hard rules (this ticket)
- READ-ONLY triage. NO: generation, promotion, canonical write, prompt modification,
  model/settings change, re-judgment of wave-1 verdicts, re-run of 348/356.
- Canonical writes under this ticket: 0. Baseline stays frozen.
- Governance lock stays ON. Opening ANY execution (full triage run, repairs, LLM wave)
  requires a NEW governance decision + a NEW execution ticket.

## Comments

- 2026-09-08: Opened per user planning decision. Awaiting approval of DRAFT v0.1
  (§§3–6: rules, field checks, artifact schema, sampling/validation plan) before any
  design implementation. NO execution ticket opened. NO generation run.
- 2026-09-08: DESIGN APPROVED WITH 4 AMENDMENTS (user policy review): (1) quotas =
  circuit breakers (examples 35%, relations_* 30% each, translations 30%,
  explanation_ar/definition_en/mnemonic 20%, sense_separation exempt); breach ⇒ HALT
  + rule review, never quota-tuning; (2) sense_separation IN-SCOPE, default
  MANUAL_REVIEW, quota-exempt; (3) examples HARD (structural) vs SOFT (grammar/POS-sense
  heuristics, escalate only on ≥2 independent signals; length→CEFR banned); (4) empty
  `[]`/`NULL` inventory ≠ defect (Validity > Inventory). Sample n=300 fixed,
  design-validation only. §7 NO-OP guard unchanged. Implementation + unit tests +
  sample ≤300 read-only AUTHORIZED from this point.
- 2026-09-08: C1 APPROVED (user formal decision): POS-gated regular-morphology
  closure (finite suffixes; no semantics/stemming/synonyms; no irregular guessing) +
  array-format branch; irregulars stay HARD; true absences stay HARD; quota 35%
  frozen; KEEP semantics unchanged. No C2, no D.
- 2026-09-08: C1 IMPLEMENTED (`lemma_form_closure` + `_phrase_variants` +
  array branch in `evaluation/field_triage.py`; `target_present` now takes pos) +
  15 new fixtures — 57/57 tests green. C1 SAMPLE RE-RUN (same 300/seed/baseline/
  quotas, read-only): PASS, no breach — manifest
  `output/triage/triage_sample_300.json` (sha `5b155e04…ac5af`, 2700 records).
  examples 23/300 = 7.67% vs 35% quota (was 47.67%). Breakdown: ~120 records
  rescued by regular morphology (plurals/tense/comparative now pass); array-format
  15/15 KEEP (0 still flagged — entire "malformed" class resolved as format);
  remaining 23 = EX_NO_LEMMA_TOKEN, all object-format: ~24 truly-absent bands
  (`just/adj` A1–B1 still visible ✓) + ~15 irregular-residue bands (`drink/drank`,
  `spend/spent`, `fly/flew`, `freeze/froze`, `drive/drove` — HARD by decision).
  Known minor residue (NOT in C1 scope, flagged honestly): possessives
  (`university's` ≠ `university` token). Other fields still 0.00% (structural
  checks on dictionary legacy; KEEP = no deterministic defect, not certified good).
  DB file hash == baseline (read-only proven). QUEUE of 23 ready for spot check
  (§10 queue list). Rules NOT yet frozen — freeze follows spot check per chain.

## 10. Sample-300 run record (design-validation; breaker fired as designed)
- Sample: `triage-sample-v1` seed, n=300, 30 CEFR×POS cells, representation quotas
  met (multi-POS 61≥15, technical 30≥10, wave-1 25≥25); 12 exception cards excluded.
  Deterministic (rebuild ⇒ identical ids). DB accessed read-only.
- Result: HALT — `examples` flag_rate 47.67% (143/300) vs quota 35%. All other
  fields 0.00% flagged; sense_separation 300 MANUAL by design (exempt).
  Records computed: 2700 (KEEP 2257 / MANUAL 300 / LLM_REVIEW 143).
- Decomposition of the 143 (read-only analysis, NOT a rule change):
  128× EX_NO_LEMMA_TOKEN (289 failing bands: ~262 inflection-blindness —
  plurals/regular inflections `years/laws/cars/universities/lasts/longer`, all
  correct English the exact-token rule cannot see — vs ~27 genuinely absent,
  e.g. `just/adj` examples never containing "just") + 15× EX_MALFORMED_JSON.
- The 15 "malformed" are a SECOND LEGACY FORMAT, not corruption: JSON ARRAY of
  strings instead of band-keyed OBJECT (e.g. `event/noun`,
  `["It was a big event.", ...]`). Deterministic format branch covers it.
- Zeros elsewhere are PLAUSIBLE (structural checks on dictionary-derived legacy:
  non-empty, valid JSON, no self-ref/dupes) — with one binding clarification:
  triage KEEP means "no deterministic defect found", NEVER "certified good".
  Semantic defects invisible to deterministic rules stay the execution wave's
  business (seeded challenger re-examines full seed); triage does not gatekeep them.
- PROPOSAL (operator, for user decision — NOT applied): C1 = regular-morphology
  closure (finite suffix rules: s/es/ies/ed/ied/ing/er/est + e-drop/doubling,
  fixture-testable, zero semantics) + array-format branch; irregulars
  (`drank/went`-class) stay HARD flags (small, reviewable, arguably worth
  surfacing). Predicted effect: flag rate collapses toward the true-defect band;
  re-run sample to measure. Alternatives if C1 insufficient: C2 (+ frozen
  irregular-verb table — lexicon ownership cost) or D (target-absence demoted to
  SOFT — loses the strongest structural signal; not recommended while the
  `just/adj` class proves the rule has teeth). Quota values stay FROZEN under
  every option (tuning banned).

  Spot-check queue (C1 run, 23 records — full detail in
  `output/triage/triage_sample_300.json`): just/adj 111 [A1,A2,B1];
  university/noun 473 [C2]; drive/noun 930 [B1]; spend/verb 1202 [B1,C2];
  drink/verb 1359 [A2,C1,C2]; theory/noun 1396 [A1]; fly/verb 1756 [B1,C1];
  specifically/adv 2094 [A1,A2]; parent/noun 2327 [C2]; communist/adj 3358
  [A1,A2]; inflation/noun 4148 [C1,C2]; freeze/verb 4331 [B2]; buyer/noun 4693
  [C1]; accurately/adv 4927 [A1]; balloon/noun 5321 [C1]; pony/noun 5666 [B2];
  variant/adj 5796 [C2]; disciplinary/adj 5899 [A1,A2];   integrate/verb 6008
  [A1,A2]; intrinsic/adj 6656 [A1]; counsellor/noun 6884 [A1,A2,B1,B2,C1];
  incline/noun 7050 [A1,A2]; possessor/noun 7264 [A1].

## 11. Spot-check evidence pack (presented 2026-09-08; NO verdict by operator)
User ruling: C1 = ACCEPTED / FROZEN CANDIDATE; distribution proves the rule, NOT
per-case correctness. The two spot-check questions (Q1 all-HARD queue-worthy?
Q2 closure wrongly KEEP anything?) are FOR THE HUMAN-OWNER. Evidence, read-only:
- Q1 full failing-band content (23 records; `passed=` bands contain the lemma):
  just/adj111 FAIL A1"He is a good man." A2"The rules are fair for everyone."
  B1"We need a fair solution to the problem." (pass B2,C1) | university/noun473
  C2"The university's endowment has grown significantly." [possessive residue] |
  drive/noun930 B1"We parked the car in the driveway." ["driveway"≠"drive" token] |
  spend/verb1202 B1"We spent a lot of money on our holiday." C2"He spent the
  entirety of his youth pursuing a lost cause." [irregular] | drink/verb1359 A2/C1/C2
  all "drank…" [irregular] | theory/noun1396 A1"It is just an idea." |
  fly/verb1756 B1"The pilot flew the plane safely." C1"Sparks flew during the heated
  debate." [irregular] | specifically/adv2094 A1"This is for you." A2"I asked for
  this one." | parent/noun2327 C2"Good parenting requires patience and consistency."
  ["parenting" derivative correctly NOT accepted] | communist/adj3358 A1"It is a
  political idea." A2"China is a big country." | inflation/noun4148 C1"Inflationary
  pressures are affecting the global market." C2"Hyperinflation rendered the currency
  practically worthless." [derivatives correctly NOT accepted] | freeze/verb4331
  B2"The police shouted, 'Freeze!'" [imperative base form — reviewer call: base
  "Freeze!" IS the lemma as token; flagged only because lowercase match? NO —
  flagged for another reason; see note] | buyer/noun4693 C1"It's a buyer's market
  right now." [possessive residue] | accurately/adv4927 A1"He counts well." |
  balloon/noun5321 C1"The national debt has ballooned in recent years."
  [denominal verb; noun closure correctly rejects +ed] | pony/noun5666 B2"The
  children brushed the pony's hair gently." [possessive residue] | variant/adj5796
  C2"These myths are merely local variants of a universal theme." ["variants" noun
  plural on an ADJ card — POS-gating behaved exactly as designed; card-or-example
  question for reviewer] | disciplinary/adj5899 A1"He broke the rules." A2"The
  school has strict rules." | integrate/verb6008 A1"Mix the parts." A2"We work
  together." | intrinsic/adj6656 A1"Gold has value." | counsellor/noun6884
  A1–C1 all "counselor" (US single-l) vs lemma "counsellor" (UK double-l)
  [spelling-variety class; 5 bands] | incline/noun7050 A1"Not used in A1."
  [placeholder junk] A2"The car went up the hill." | possessor/noun7264 A1"He is
  the owner."
- NOTE on freeze/verb B2 "'Freeze!'": base-form token present ("freeze"); flag cause
  is leading-capital+punct? NO — those are SOFT. Operator does NOT explain away:
  listed for reviewer; if the engine is wrong here it is a rule bug to fix.
- Q2 rescued-via-inflection audit: 236 bands (same sample) now KEEP via forms
  years/lasts/longer/laws/cars/meets/programmed/mothers/levels/parked/taxed/
  completed/… — every inspected match a textbook regular inflection; ZERO
  derivatives/synonyms observed in audit; rejection boundary holds
  (parenting/inflationary/hyperinflation/ballooned correctly unaccepted).
- Awaiting human verdict: DESIGN VALIDATED / RULES FROZEN, or named rule fix +
  same-sample-same-seed repeat. Quota frozen either way. No full run regardless.

## 12. Closing verdict (human-owner, 2026-09-08): DESIGN VALIDATED / RULES FROZEN
- C1: ACCEPTED + FROZEN. Spot-check: PASS. No sample repeat.
- Recorded findings: false acceptance 0 in the 236-band audit; true-missing defects
  caught (`just/adj`, `incline` placeholder, `communist`, …); derivatives rejected
  (`parenting`, `inflationary`, `hyperinflation`, `ballooned`); synonyms rejected;
  POS gating works (`variant/adj` vs noun plural; noun has no +ed so `car/cared`
  impossible); regular morphology bounded and successful; irregulars stay HARD queue;
  possessives a known residual outside C1.
- Quotation micro-bug (`"'freeze" ≠ "freeze"`, quote-glued token): recorded as
  KNOWN_MICRO_BUG / known limitation — explicitly NOT fixed now. Rationale (user):
  a tokenization artifact, not a lexical-semantics or C1-rule problem; touching the
  implementation post-validation without operational need is rejected. NOT a failed
  gate; does not block the freeze.
- Frozen: rules v0.1 + C1 as implemented in `evaluation/field_triage.py`
  (+ 57 unit tests); sample evidence `output/triage/triage_sample_300.json`.
  Baseline unchanged. Canonical writes under this ticket: 0.
- NEXT (not this ticket): a SEPARATE governance decision for the 7,300 READ-ONLY
  full triage — authorizing ONLY running `field_triage.py` over the full population.
  No generation, no promotion, no canonical write. After it: the field-by-field map.
- 2026-09-08: Governance decision requested as Ticket 18
  (`18_full_dataset_field_triage.md`, PENDING — run-only authorization, no
  generation/promotion/write). This ticket stays CLOSED; nothing further happens
  here regardless of the Ticket 18 ruling.

(append operator notes below this line; newest at the end)
