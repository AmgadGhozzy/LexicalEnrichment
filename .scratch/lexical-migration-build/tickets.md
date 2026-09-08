# Build tickets — combined file (read-only convenience copy)

> BT-13 lives in `issues/13_linguistic-evaluation.md` and at the
> end of this file (added after the original 12).

Source of truth remains the per-ticket files under `issues/`
(same directory). This file is a single-file convenience copy for
review; to change a ticket, edit its `issues/` file, then regenerate
this copy.

Spec: `../lexical-migration-wayfinding/spec.md` (accepted).
Decisions: `../lexical-migration-wayfinding/map.md` + `issues/01–12`.
Graph: frontier 01, 02, 03, 04, 05 → mid 06, 07, 08 → late 09, 10,
11 → 12 → 13. Statuses live in each ticket file.

---

# 01: Gate A — external CEFR source selection (BT-01)

**What to build:** the closed Gate A decision — a named authoritative
external CEFR lexicon/source with pinned version and an explicit
versioned source-precedence order — recorded as a decision that
unblocks canonical CEFR assignment. No code, no migration; a decision
with cited provenance.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Spec ref:** spec §2 (CEFR) + Gate A; wayfinding 08 (legacy CEFR =
evidence, no auto-authority; curriculum/difficulty/LLM barred).

## Decision record (Gate A closed as decision; operational prerequisite open)

- Primary: Cambridge EVP (authoritative for covered lexical senses).
  Exact release/version + access/retrieval date TO BE PINNED at
  license acquisition.
- Secondary (corroborating only): CEFR-J v1.6 (2020-03-24),
  EFLLex (LREC 2018 release). File versions/hashes pinned at acquisition.
- Mechanical precedence: EVP authoritative where covering; others
  corroborate only; legacy = history. EVP silence → value stays
  unresolved; no inference from curriculum/difficulty/frequency/
  IELTS/LLM.
- Operational prerequisite: EVP license/access acquired and pinned
  before any canonical EVP-based CEFR assignment; lack of access
  blocks execution, never triggers silent fallback.

- [ ] Authoritative external CEFR source named with exact version
- [ ] Precedence order over versioned evidence written explicitly
- [ ] Legacy-CEFR handling under the new policy stated (evidence stays)
- [ ] Decision recorded; BT-10 CEFR-stratum OPEN note cleared or restated
- [ ] Record states at minimum: source name, exact version/release,
  retrieval/provenance reference, CEFR value representation,
  explicit precedence order against other CEFR evidence, and
  effective date/version of the decision (no generic source names)
- [ ] No other ticket's scope changed by this decision

---

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

1. Vintage identity — UNLOCATED. On disk only: `WordsMaster.db`
   (7,300, 2026-03-02), `LexicalStaging.db` (8,027, 2026-09-03),
   `IeltsWord.db`; no backups. Staging was built from a
   post-March ≥8,027-row WordsMaster revision not on disk.
   Entry rule: CONTINUED QUARANTINE (identification ≠ admission).
2. 692-vs-695 gap — RECONCILED as draft-prose error: artifact
   121+571+32+3 = 727 closes exactly; draft 695+32+3 = 730 never
   closes; 692+3 = 695 explains the figure as the main block plus
   double-counted new lemmas. "695" struck; decomposition stands
   unconditionally; gap item closed.

Gate B state: investigation resolved; MIGRATION PRECONDITION
PERSISTS — no staging-sourced row migrates until the vintage is
located or rows are individually adjudicated.

- [ ] 8,027 vintage identified and documented with evidence
- [ ] Entry rule for vintage rows stated (or continued quarantine)
- [ ] 692-vs-695 gap reconciled against the artifact (no invented values)
- [ ] Reconciliation establishes provenance/matching ONLY — resolving
  the gap does not authorize promotion of any of the 727 rows to
  canonical data; quarantine stands until per-item review says otherwise
- [ ] 121+571+32+3 authority status confirmed or explicitly superseded
- [ ] No staging row promoted to canonical data by this ticket

---

# 03: #2-vs-#3 machine-testable mapping rule (BT-03)

**What to build:** the locked, machine-testable rule distinguishing
cascade #2 (NORMALIZED_LEMMA_EXACT) from #3
(SAME_LEMMA_DIFFERENT_POS), proven against the 1,022-row artifact —
so the two classifications can never overlap and IELTS mapping
execution has an unambiguous input.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Spec ref:** spec §3 (OPEN blocking verification item); wayfinding
05 (cascade, classification ≠ creation); 02 (folding), 03 (POS).

## Locked rule (verified read-only over `ielts_mapping.json`)

First-match-wins order: #4 whitespace → #5 no candidate → #2 POS
absent/unmappable → #1 mapped POS held → #3 mapped POS not held →
#6 otherwise. Mechanical run on 1,022 rows: 678/0/34/34/276/0,
identical to baseline, overlaps=0. #2 vacuous on this source
(retained for POS-less future sources).

- [ ] #2 vs #3 rule stated in testable form (absent/non-comparable
  POS vs explicitly present differing POS, or artifact-proven better)
- [ ] Rule verified mechanically against the artifact; overlaps = 0
- [ ] 678/34 baseline disposition stated (hold or deterministically revise)
- [ ] BT-07 unblocked on the rule side (still needs BT-04, BT-06)

---

# 04: Identity folding + key implementation and tests (BT-04)

**What to build:** a tested deterministic normalizer implementing the
locked folding contract (trim, lowercase, NFC, single-space,
diacritics preserved; hyphen/whitespace/apostrophe rules;
possessive→base; lemma-level; names/brands excluded) plus the
`(normalized_lemma, canonical_pos)` key builder under the locked
11-tag enum (one POS per identity, composites rejected) — with unit
tests covering hyphen, whitespace, apostrophe, and diacritics cases.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Spec ref:** spec §1; wayfinding 02 (full contract), 03 (enum, one
POS, dependency contract).

## Implementation record

- New `evaluation/identity.py` + `evaluation/test_identity.py`:
  16 passed (folding, admissibility, key, enum lockstep both schemas).
- Fixed during execution: curly-apostrophe folding bug (caught by new test).
- Pre-existing suite: 30 passed + 1 unrelated pre-existing failure
  (missing `gemini_flash_v1.1_batch_pilot.json` fixture).

- [ ] Folding implements every locked sub-rule, nothing invented
- [ ] Key builder enforces 11-tag enum + single POS; composites refused
- [ ] Unit tests green incl. hyphen/whitespace/apostrophe/diacritics
- [ ] Zero-derivation legitimacy NOT judged here (deferred to 03
  adjudication at execution time)

---

# 05: LLM-versioning instrumentation (BT-12)

**What to build:** versioning instrumentation capturing all 7 locked
provenance dimensions on every LLM output (prompt id/version, schema
id/version, provider, model id/version, generation config incl.
temperature, thinking/grounding config, experiment/run IDs,
timestamp, input snapshot/hash, output hash, status) with
append-only history — in place before any pilot output exists.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Spec ref:** spec §4 (LLM versioning); wayfinding 11 (DEFERRED,
anti-forgetting clause); v2.2.3 held as candidate only.

## Implementation record

- New `evaluation/run_provenance.py` + `evaluation/test_run_provenance.py`:
  10 passed (completeness per group/field, hash+status enforcement,
  append-only, defective append refused). No update/delete API exists.
- Suite: 55 passed (new + identity + validator + utils). Pre-existing
  `test_input_builder_determinism` failure UNCHANGED (missing fixture),
  not repaired here. No runner rewiring, no config promotion.

- [ ] All 7 dimension groups recorded per output, none omittable
- [ ] Regen creates a new history record; no silent replace path
- [ ] Input snapshot/hash captured (not just model identity)
- [ ] BT-11 cannot produce untraceable output after this lands

---

# 06: Versioned frequency observations + dense rank (BT-05)

**What to build:** versioned frequency-observation recording
(wordfreq Zipf; source/version/lang/metric/observed_at, corpus
identity kept separate) with deterministic dense-rank derivation
per pinned version (ties share rank; alphabetical lemma is
display-order only) — verified on pinned fixtures, legacy
rank/frequency preserved untouched and never consumed.

**Blocked by:** 04 (identity folding + key).

**Status:** resolved

**Spec ref:** spec §2 (frequency); wayfinding 01 (Zipf canonical,
provenance, dense rank, legacy preserved, stable IDs).

## Implementation record

- New `evaluation/frequency.py` + `evaluation/test_frequency.py`:
  11 passed (dense ties, order independence, mixed-scope refusal,
  scope partition, pin/zipf validation, no-DB-footprint).
- Mixed-scope silent merge caught and fixed pre-test (now ValueError).
- Suite: 66 passed. Pre-existing fixture failure unchanged.

- [ ] Observations self-describe version; upgrades add versions
- [ ] Dense rank deterministic per pinned version on fixtures
- [ ] No unique-ordinal ranks; no id=rank resurgence
- [ ] Legacy rank/frequency columns byte-identical before/after

---

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

- New `evaluation/evidence_schema.py` (INSERT-only helpers) +
  `evaluation/test_evidence_schema.py`: 10 passed on `:memory:`
  (structure, enum/FK enforcement, `is_ielts` VIEW derived-only +
  non-writable, quarantine/identity ID separation, snapshot
  immutability). No repo DB touched; no canonicalization runs;
  carried notes updated: BT-01 resolved, canonical CEFR assignment
  still BLOCKED pending EVP release + license; BT-02 resolved,
  vintage UNLOCATED, staging rows quarantined.

- [ ] Schemas hold every locked field; quarantine ID ≠ identity ID
- [ ] Provenance append-only; snapshot identity immutable
- [ ] `is_ielts` has no independent write path (projection or
  recomputed cache only)
- [ ] BLOCKED notes carried: no canonical CEFR values (BT-01
  open); no 8,027 rows admitted (BT-02 open)

---

# 08: Deterministic repairs + CI guard (BT-09)

**What to build:** the settled deterministic repairs with
before/after counts (UK-IPA fallback with `fallback_from_us`
provenance, never LLM; grounding-artifact removal incl. the two
known leaks) plus the CI/validation guard rejecting URLs,
grounding markers, and citation artifacts in learner-facing
fields — all verified through the staging-audit seam.

**Blocked by:** 07 (evidence/quarantine schemas).

**Status:** resolved

**Spec ref:** spec §4 (legacy enrichment handling), §6; AGENTS.md
IPA + syllabification rules (NULLs preserved, no LLM).

## Implementation record

- New `evaluation/deterministic_repairs.py` +
  `evaluation/test_deterministic_repairs.py`: 13 passed (fallback
  provenance, artifact removal with Arabic/IPA/CJK preserved,
  guard codes, exact before/after counts, non-mutation).
- Suite: 89 passed. Pre-existing fixture failure unchanged. No
  application to real rows (execution scope).

---

# 09: Deterministic IELTS mapping execution (BT-07)

**What to build:** the executed 1–6 cascade over all 1,022 IELTS rows
using the locked 02 folding, 03 POS policy, and BT-03 #2-vs-#3 rule —
producing the versioned mapping artifact with full per-row
provenance and verified counts against the 678/34/276/34/0
baseline (mechanical deltas only, explained row by row).

**Blocked by:** 03 (mapping rule), 04 (identity), 07 (schemas).

**Status:** resolved

**Spec ref:** spec §2 (IELTS cascade, evidence-only, gated pool);
wayfinding 05.

## Execution record

- New `evaluation/ielts_cascade.py` + `evaluation/test_ielts_cascade.py`:
  10 passed (order, short-circuits, schema integration).
- Full 1,022-row run → new `output/ielts_mapping_v2.json`:
  678/0/34/34/276/0, zero mechanical delta, frozen input untouched.
- Suite: 99 passed. Pre-existing fixture failure unchanged.

- [ ] All 1,022 rows classified exactly once; counts verified
- [ ] No canonical field overwritten by any IELTS value
- [ ] Duplicates kept as separate topic rows; multiwords routed
  to quarantine, none minted as identities
- [ ] 276-row pool emitted as candidates only (creation is BT-10
  scope or later, never here)

---

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

- New `evaluation/quarantine.py` + `evaluation/test_quarantine.py`:
  5 passed (727 class-complete, 34/34 multiwords, no-promotion,
  BT-07 schema fit, zero identities minted).
- New `output/quarantine_v1.json`. Per-row 727 materialization
  BLOCKED on Gate B (stated, not done). Suite: 104 passed.

- [ ] 727/727 accounted; 34/34 multiwords preserved as quarantine
  evidence with topics attached — never split into identities,
  never minted as single-word records
- [ ] No quarantined row promoted without its applicable review
- [ ] BLOCKED: vintage entry rule awaits BT-02; OPEN: 692 gap
  awaits BT-02 reconciliation
- [ ] Quarantine completeness asserted by test, not prose

---

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

- New `evaluation/pilot_manifest.py` +
  `evaluation/test_pilot_manifest.py`: 7 passed (allocation,
  determinism, exclusions, OPEN flag, hash stability).
- Frozen `output/pilot_manifest_v1.json` (f76443bac76a9883):
  1,000 entries; 0 golden / 0 prior picked; CEFR evidence-label
  strata with OPEN re-stratification flag; rerun hash-identical.
- Three read-only SELECT passes only; zero writes. Suite: 111.

- [ ] Strata/quotas/seed/allocation explicitly decided (no
  convenience strata)
- [ ] Manifest frozen with hash; exclusions verifiable
- [ ] OPEN: CEFR-stratum shape contingent on BT-01 (Gate A) —
  manifest must not assume canonical CEFR before it closes
- [ ] No pilot execution in this ticket (BT-12 scope)

---

# 12: Pilot execution — regen, validation, eval prep (BT-11)

**What to build:** the executed pilot: canonical example
regeneration under the 07 contract on v2.2.3 (experimental
candidate only) with full LLM-versioning capture, automated
validation through the validator + staging-audit seams, and the
blind human-evaluation package per the locked equalized-review
design — reported as experiment evidence, never a
production-readiness claim.

**Blocked by:** 08 (repairs), 11 (manifest), 05 (LLM versioning).

**Status:** partial — FINAL ACCOUNTING 354+2+644=1,000.
354 execution-success (no quality claim); 2 partial =
identity-validation limitation (ice-cream/line-up, validator
unadjusted); 644 infra-empty, no attribution, no blind retry;
probe 3/3 direct-success → batch-specific; linguistic quality
UNASSESSED; zero canonical writes; no promotion. NOT resolved.

**Spec ref:** spec §4 (examples, LLM status), §7 (pilot,
evaluation); wayfinding 06 (difficulty untouched), 07, 11.

## Execution record

- New `evaluation/pilot_run.py` + `evaluation/test_pilot_run.py`:
  7 passed (stubs + nullable-transport both schema paths).
- Amendment: validator bypassed its own nullable converter;
  fixed (idempotent convert at validate_schema entry; no schema
  or semantics change; characterization green).
- Live smoke-2 (RUN-SMOKE-2, new dir, smoke-1 immutable): ok,
  zero failures, guard clean, history captured.
- Suite: 138 passed. Full 1,000 NOT run — awaiting authorization.

- [ ] Regen obeys exact-token + sense/POS + no-length-CEFR rules
- [ ] Every output carries complete versioning (BT-05
  instrumentation verified, no untraceable rows)
- [ ] Human eval blind, field-by-field, identity map separate
- [ ] Report states experiment evidence only; Gates A/B status
  restated, not assumed away

---

# 13: Blind linguistic evaluation package for the 354 (BT-13)

**What to build:** frozen blind A/B package (354 items, sides
seeded A167/B189, identity map separate, blank 7-field ballots +
7-class critical checklist). Judging is future human work.

**Blocked by:** 12 (pilot outputs) — inputs frozen, no regen.

**Status:** partial — package frozen (`output/eval_blind_v1/`:
`eval_blind_v1.json` + PRIVATE `eval_identity_map.json` +
`eval_input.json`, input hash bf7a1479…), ballots blank, zero
verdicts. Comparator: ro legacy rows for the 354 ids (single
pass). No regen, no canonical writes. Leak rule: identifier
shapes only (two live false positives on content words fixed +
regression-tested).
