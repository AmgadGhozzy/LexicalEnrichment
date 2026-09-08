Status: ready-for-agent

# Spec: LexicalEnrichment Canonical Migration & Data-Quality Architecture

Source map: `.scratch/lexical-migration-wayfinding/map.md` + `issues/01–12` (all resolved).
Each locked `## Answer` below is normative. Open items are marked OPEN and
must not be treated as decided.

## Problem Statement

LexicalEnrichment holds a 7,300-row legacy flat table (`WordsMaster.db`,
table `wordsMaster`, 39 columns) whose key fields carry unreliable
semantics: `rank == id` for 7,300/7,300 (row identity, not frequency),
CEFR/frequency provenance unknown, ~29% of difficulty scores
clamp-tautological, 14.8% of 43,800 legacy example cells failing
exact-lemma check with CEFR assigned by sentence word count, and an
8,027-row staging shell whose 727 extra rows mix malformed POS,
mixed-legitimacy expansions, and 3 brand-new lemmas. A 1,022-row IELTS
source overlaps (712) and extends (310) the lexicon but has been used
without a matching policy. Any migration built on these foundations
without locked decisions reproduces the same forensic problems at
larger scale.

## Solution

A canonical layered data architecture that separates lexical identity,
versioned frequency, CEFR evidence, IELTS evidence, LLM enrichment,
word relations, examples, and curriculum placement — migrated
additively and reversibly from frozen snapshots, with every
transformation deterministic, provenanced, and validated through the
existing validator / staging-audit / hash-manifest seams. No new
lexical identities, no pilot, and no production migration until the
two hard gates (external CEFR source selection; 8,027-vintage
reconciliation) are explicitly closed.

## User Stories

1. As a data engineer, I want every lexical identity keyed by
   `(normalized_lemma, canonical_pos)` under a locked folding contract,
   so that dedupe and matching are deterministic across sources.
2. As a data engineer, I want frequency stored as versioned
   observations (wordfreq Zipf, pinned version/lang/metric) with dense
   rank derived per version, so that ranks are reproducible and never
   confused with identity.
3. As a curriculum designer, I want CEFR as versioned external evidence
   with an explicit precedence policy, so that no model, curriculum
   slot, or heuristic silently rewrites proficiency truth.
4. As a data engineer, I want IELTS mapped through a deterministic
   1–6 cascade into evidence rows (never overwriting canonical fields),
   so that overlap, candidates, multiwords, and malformed rows are
   auditable counts, not prose estimates.
5. As a QA reviewer, I want `is_ielts` as a derived-only boolean
   projection of approved evidence, so that the flag can never disagree
   with its source of truth.
6. As an auditor, I want all legacy values preserved with snapshot
   identity and append-only provenance, plus mandatory backups and
   additive-only migration, so that every stage is reversible and
   reconstructible.
7. As a learner-content lead, I want 3 exact-token, sense-aligned,
   human-gated examples per identity (legacy grid preserved untouched),
   so that regeneration fixes quality instead of reshuffling cells.
8. As a data engineer, I want legacy difficultyScore quarantined as
   historical evidence with any redesign gated on proven signal, so
   that a recycled heuristic is never presented as measurement.
9. As an ML engineer, I want every LLM output traceable across 7 locked
   provenance dimensions (append-only history), so that experiments are
   reproducible and pilots are shippable only with full lineage.
10. As a curriculum designer, I want curriculum placement as a
    downstream pedagogical operation (identity → evidence → unit, IDs
    never renumbered), so that pedagogy stays revisable while identity
    stays stable.
11. As a reviewer, I want the stratified pilot manifest frozen with
    hash/seed/exclusions (excluding Golden 160, prior experiment words,
    quarantined and malformed candidates), so that the pilot measures
    the architecture instead of the sampling.
12. As a governor, I want Gates A (external CEFR source) and B
    (8,027-vintage reconciliation) explicitly surfaced as blockers, so
    that implementation cannot silently resolve what wayfinding left
    open.

## Implementation Decisions

### 1. Canonical identity + normalization (02, 03)

- Identity key: `(normalized_lemma, canonical_pos)`. Stable IDs are
  permanent and independent of rank, frequency, CEFR, curriculum,
  IELTS, and enrichment.
- Deterministic folding: trim; lowercase; Unicode NFC; collapse inner
  whitespace to one space; diacritics preserved exactly, never
  stripped.
- Hyphenated form without whitespace = single-word candidate; any
  form with whitespace = multiword candidate (→ §3).
- Possessive `'s` maps to base lemma (never an identity); internal
  apostrophes preserved; other punctuation = inadmissible.
- Lemma-level identities only; inflected surface forms never separate
  identities. Zero-derivation legitimacy is adjudicated per item via
  §1 POS policy, never pre-judged here.
- Proper names and brands excluded. Abbreviations/acronyms admissible
  only as lexicalized common items with approved canonical POS.
- Canonical POS inventory locked to the 11-tag enum
  (adj, adv, conj, det, excl, modal, noun, num, prep, pron, verb) per
  `evaluation/prompts/schemas/lexical_output.v1.json` (identical in
  v1.1-candidate). One POS per identity; composites (`noun+verb`)
  are source anomalies held as review evidence, never stored.
- Dependency contract: 02 defines normalization + key; 03 defines
  canonical POS; canonicalization requires both.

### 2. Source/evidence model (01, 08, 05, 09, 10)

- Frequency: wordfreq Zipf canonical (closes the AGENTS.md vs
  DECISION_LOG.md contradiction). Observations record source,
  pinned package version, language, metric=zipf, observed_at
  (plus corpus/model identity where exposed, never conflated with
  package version). Dense `lexical_rank` by descending Zipf per
  pinned version; ties share rank; alphabetical lemma is
  display-order only. Legacy rank/frequency 1–6 preserved, never
  consumed. New identities get new stable IDs; no renumbering;
  upgrades produce new versioned derivations, never silent rewrites.
- CEFR: external evidence, separate from curriculum, difficulty,
  frequency, identity, IELTS, enrichment. Curriculum and difficulty
  barred as inputs (difficulty already depends on CEFR — circular
  otherwise). LLM CEFR is versioned evidence-only. Legacy CEFR =
  preserved evidence, no auto-authority (unknown provenance).
  Canonical CEFR only via an explicit versioned precedence policy.
  Gate A (external CEFR lexicon selection) is an explicit blocking
  decision ticket that must close before any canonical CEFR assignment
  during migration: no CEFR canonicalization runs, and no
  implementation ticket selects a lexicon, version, or precedence
  order on its own. Until Gate A closes, legacy CEFR remains
  evidence only.
  Storage: one canonical value per identity + versioned evidence
  history, no destructive overwrite.
- IELTS: deterministic cascade NORMALIZED_LEMMA_POS_EXACT (678) →
  NORMALIZED_LEMMA_EXACT → SAME_LEMMA_DIFFERENT_POS (34) →
  MULTIWORD (34) → NEW_SINGLE_WORD (276) → UNRESOLVED_MALFORMED
  (0); total 1,022 (712 overlap + 310 unrepresented). Matching only
  against the 02/03 universe; classification ≠ creation; canonical
  POS never overwritten by IELTS. Duplicates stay separate topic
  rows. IELTS contributes presence/topics/provenance/evidence/
  discovery; overwriting canonical definition, Arabic, IPA,
  examples, CEFR, frequency, difficulty, or curriculum is barred.
  The 276 form a gated pool (02/03 gates, no auto-creation, no
  pilot by appearance). Mapping provenance sufficient to
  reconstruct every classification; physical DDL deferred to build.
- `is_ielts`: derived-only boolean projection of approved evidence
  (1 iff ≥1 approved row resolves to the identity); no independent
  write path; stale cache = defect, never second truth; raw or
  quarantined rows never set it; storage (column vs view) decided
  at build.
- Provenance: every legacy row traceable via source name/version,
  snapshot hash, row ID, import timestamp, operation ID. Snapshot
  identity immutable; provenance append-only.

### 3. Data admissibility (04, 10, 02/05 items)

- MULTIWORD_QUARANTINE adopted: whitespace forms are atomic
  quarantined expressions — never split into pseudo-identities,
  never assigned component POS, never minted as single-word
  identities. Quarantine records preserve original + normalized
  form, provenance, classification, status (DDL at build).
  Quarantine ID ≠ lexical-identity ID. The 34 IELTS multiwords
  keep topics in quarantine. Dedicated multiword architecture is a
  separate future decision.
- 727/vintage: the 8,027-source is a distinct unlocated vintage;
  identifying it is a migration precondition (Gate B). Until Gate B
  closes, 8,027-source rows remain quarantine/source evidence only:
  "record + flag" never authorizes treating them as canonical data
  or picking a closest vintage. The 727 are
  quarantined forensic source (121 implausible-POS + 571
  zero-derivation-mixed + 32 same-lemma-diff-POS + 3 new), reviewed
  per item, never bulk-migrated, never deleted.
- OPEN item: 692-vs-695 arithmetic gap (121+571=692≠695) carried as
  an unresolved forensic discrepancy; the 121+571+32+3
  decomposition stays authoritative pending reconciliation, and it
  is not a conceptual blocker to the identity policy.
- OPEN blocking verification ticket (must close before any IELTS
  mapping execution): the mapping artifact must define a
  machine-testable rule distinguishing cascade #2
  (NORMALIZED_LEMMA_EXACT) from #3 (SAME_LEMMA_DIFFERENT_POS) —
  candidate shape: #2 applies when the normalized lemma matches an
  existing identity and the IELTS POS is absent or non-comparable
  under a stated rule; #3 applies when the IELTS POS is explicitly
  present and differs from the canonical POS. This candidate
  wording is illustrative, not adopted: the distinction must be
  proven against the artifact before it is locked. The
  678/34/276/34 counts remain baseline only until mechanical
  verification under the locked 02 folding contract.

### 4. Enrichment (07, 06, 10, 11)

- Examples: 3 per identity default; 4th/5th only for genuine
  polysemy with declared traceable sense (never padding, never
  CEFR-bucket filling; legacy 6-cell grid not canonical). Exact
  normalized-lemma standalone token, no exceptions (no
  inflection/derivation/synonym substitutes). POS+sense fit,
  natural grammatical English, contextual variation, no
  placeholder/metadata leakage. Word count never certifies CEFR
  (diagnostic at most). Full regeneration; legacy 43,800 cells
  preserved unchanged, no sentence-by-sentence repair. Structural
  validation (target presence, machine-checkable sense fit, no
  leakage, schema) ≠ quality pass; naturalness, sense fit, and
  CEFR fit stay human-gated.
- Difficulty: legacy score LEGACY ONLY — never migrated as truth,
  never consumed (not as CEFR/frequency/identity/curriculum
  input), never presented as measured. Staging recompute rejected
  outright (unknown computation). Future redesign gated: recompute
  transparently from real frequency rank + documented syllable
  handling with explicit weights, plus proven signal beyond
  CEFR+frequency. No redesign approved here.
- Legacy enrichment: field-level KEEP/REPAIR/REGENERATE only, no
  blind mass regen. Deterministic removal of known grounding leaks
  (`homemade`.definitionAr, `migrate`.usageNote); CI/validation
  rejects URLs, grounding markers, and citation artifacts in
  learner-facing fields.
- LLM versioning (must resolve before any pilot): every output
  traceable across prompt id/version, schema id/version, provider,
  model id/version, temperature + other material generation
  parameters, thinking/grounding config, experiment/run IDs,
  timestamp, input snapshot/hash, output hash, status;
  append-only history (regen = new version, never silent replace).
  v2.2.3 held as experimental candidate (HR-104), not production
  truth; no broad sweeps until architecture + deterministic
  preprocessing settle.

### 5. Curriculum (12)

- Creation order: pass 02 → pass 03 → mint stable ID → provenance
  → frequency observation → CEFR evidence (08) → IELTS evidence
  (05) → curriculum last. IDs never renumbered; failed candidates
  get no identity.
- `unitId` is a reassignable pedagogical bucket; never derived
  from rank, frequency, CEFR, IELTS presence, or ID
  (rank != CEFR != unit; ID != unit). Placement follows teaching
  logic; the placement algorithm itself is a separate spec
  concern, explicitly not defined here.
- IELTS identities only from the approved 276 pool; mapping
  creates neither identities nor units.
- Legacy unit associations = historical evidence (inform, never
  constrain); re-bucketing allowed without touching ID, rank,
  CEFR, or evidence.

### 6. Migration/reversibility (10)

- Additive and reversible: new structures alongside legacy; never
  overwrite in place; no destructive transformation.
- Frozen inputs: 7,300-row WordsMaster snapshot
  (`cfabafa8…86984f`), Golden Set v2 (160, `2a179128…2821`),
  `evaluation/forensic_audit/*`, root `DECISION_LOG.md`.
- Provenance and identity of hashes: source snapshot identity
  (which frozen input a row came from) is recorded separately from
  operation/output hashes (what a migration or generation step
  produced). A `source_row_id` alone never admits a row into the
  migration path.
- Verified backup (`*_backup_<timestamp>.db`) before any DB
  mutation. A stage is auditable only if inputs, outputs,
  provenance, and operation identity are reconstructible without
  mutable application state.
- Preservation ≠ museum: history must stay recoverable and
  auditable; active-vs-archive placement is physical design.

### 7. Pilot specification

- Universe: verified 7,300 + approved clean IELTS candidates only.
  Exclusions: Golden 160, prior experiment words, quarantined /
  unresolved / malformed candidates (incl. all 727 until
  individually approved).
- Manifest frozen with candidate IDs, source snapshot hash,
  selection algorithm, seed, exclusions/replacements, manifest
  hash. Stratification dims graduate from 01+08 (frequency
  source/version, CEFR precedence); deterministic repair scope
  from 10; quarantine handling from 04/05/10. Stratification
  stays deferred by design: ticket dependencies must enforce
  01+08 → pilot-stratification decision → frozen manifest →
  pilot, so no pilot implementation ticket runs before the
  manifest-spec decision locks strata, quotas, seed, and
  allocation. No agent-selected convenience strata.
- Execution on v2.2.3 as experimental candidate; automated
  validation through the validator seam + staging-audit seam;
  blind human evaluation per locked equalized-review design
  (field-by-field, no collapsed overall score, identity map kept
  separately). Pilot results are experiment evidence, never a
  production-readiness claim.

## Testing Decisions

- Good tests here assert artifact properties and DB invariants,
  never model opinions: exact-token presence, enum membership,
  one-POS-per-identity, dense-rank determinism per pinned
  version, quarantine completeness (727/727 accounted, 1,022
  rows classified exactly once), manifest hash stability.
- Seams: (1) `evaluation/lexical_validator.py` artifact seam for
  enrichment outputs; (2) `qa/verify_staging_integrity.py` DB-audit
  seam extended to migration stages (provenance, IPA rules, tags,
  JSON↔SQLite parity); (3) `evaluation/utils.py` canonical_hash +
  golden-gated I/O for freezing manifests and the deterministic
  mapping recompute.
- Prior art: `evaluation/test_lexical_validator.py`,
  `evaluation/test_utils.py`,
  `evaluation/test_batch_infrastructure.py`,
  `evaluation/test_validator_characterization.py` (enum lockstep).
- New coverage required at build: folding/identity unit tests
  (incl. hyphen/whitespace/apostrophe/diacritics cases),
  dense-rank + tie tests on pinned fixtures, quarantine
  no-promotion tests, `is_ielts`-derivation tests, provenance
  append-only tests, LLM-dimension completeness tests.
- Quality gates that stay human: sense fit, naturalness,
  CEFR-appropriateness, mnemonic/definition Arabic quality —
  structural green is never a quality pass.

## Out of Scope

- The 21 LEX implementation tickets as a backlog; implementation
  tickets follow only after this spec is reviewed and accepted.
- 8K runs, production migration, schema/model-matrix comparison
  (governance lock until content-QA gate passes).
- Golden Set modification; forensic artifact regeneration;
  727 bulk migration or deletion; IELTS-as-CEFR/frequency truth;
  LLM-regenerated IPA; manufactured syllabification;
  sentence-length CEFR; broad model/temperature sweeps.
- Physical DDLs, the pedagogical placement algorithm, the
  multiword architecture, the difficulty redesign, and the
  external CEFR lexicon choice — all explicitly deferred items
  with named owners (spec sections above), not silent gaps.

## Further Notes

- Vocabulary discipline: identity ≠ frequency ≠ rank ≠ CEFR ≠
  curriculum ≠ IELTS evidence ≠ LLM enrichment ≠ relations — in
  code, columns, docs, and review language alike.
- Hard Gate A (external CEFR source selection: blocking decision
  ticket before any canonical CEFR assignment) and Hard Gate B
  (8,027-vintage reconciliation: source quarantined until proven)
  block implementation, not specification. The spec surfaces them
  as explicit decisions; it does not invent a precedence rule or
  launder the 8,027 rows into canonical data.
- The five carry-forwards ride with the spec as open
  specification/verification items: CEFR lexicon selection,
  vintage reconciliation, 692-vs-695 gap, #2-vs-#3 distinction,
  LLM physical DDL (+ placement algorithm, quarantine DDL, pilot
  stratification detail at build).
- Governance lock persists through spec generation: Golden Set,
  forensic artifacts, `DECISION_LOG.md`, and databases frozen.
