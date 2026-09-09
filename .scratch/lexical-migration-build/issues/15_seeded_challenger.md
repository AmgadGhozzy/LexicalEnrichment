# 15: Seeded regeneration experiment (EXP-SEEDED-001, BT-15)

**What it is:** the Challenger arm to the Legacy Champion — a
seeded (legacy-aware) field-level regeneration of the same 356
blind-package entries, evaluated with the same DTO, same 7 fields,
same critical taxonomy, same deterministic validator, and the same
FROZEN AI judge (ai-rubric-v3) for the first comparison. Not a
validation of the judge — an evidence package on whether the
legacy-oriented editor beats/replicates the frozen legacy.

**Champion:** legacy_v1 (frozen). **Challenger:** seeded_v1.

**Gate context:** BT-14 closed PARTIAL / SUFFICIENT FOR METHOD
DECISION at 241/356. Production judge NOT authorized. Rule: AI is
never sole arbiter; blind evaluator = human + AI judge v3 frozen.

## Locked constraints
- Golden frozen (golden_v2 sha256 `2a179128…2821`). No new golden.
- Legacy reference frozen; seeded candidate is a NEW experiment.
- Never touch `eval_identity_map.json` (identity via (lemma,pos)).
- Seed DTO = transport normalization only, NO semantic cleaning.
- `rank`/`frequency`/`difficultyScore` NEVER passed to the LLM.
- field_decisions {action, reason} live in PROVENANCE, never the
  canonical learner record.
- No single threshold: field-level promotion gate (mosaic = success).
- 3 examples max; exact lemma token in every example; NULL preferred
  over a bad mnemonic; CEFR/POS/identity immutable.
- Post-scale human audit (10–15 cards, stratified, seed 356014)
  remains REQUIRED after generation.

## Prompt
`evaluation/prompts/lexical_enrichment_seeded_v1.txt` (verbatim
user text; sha256 `064fd6cc880338b560127426b3cd3ab3a5e95f42c65b3c8708b617613b6e0347`).
Output contract: schema-only JSON (lemma, pos, cefr, definition_en,
explanation_ar, senses, examples(3), translations, relations,
mnemonic, phonetic_us/uk, syllables, semantic_tags, ai_confidence).
Decisions declared post-hoc in a SEPARATE audit call → provenance.

## Artifacts (either present or pending)
- `output/EXP-SEEDED-001/seed_snapshot_v1.jsonl` (+.sha256
  `197089b30819bf708c61b5ed065a4b829a2c430afddf302ec1bd3d8a642717f3`) —
  356 records, 0 missing, 0 ambiguous via (lemma,pos).
- `evaluation/configs/seeded_batch_config.json` — run config.
- `output/EXP-SEEDED-001/generated/seed_generation.../` →
  `raw/`, `seeded_generation_provenance.jsonl`, `progress.json`
  (planner: raw/, seeded generation provenance, seeded_validator
  report, seed field diff, blind package v2, promotion report).
- Pending: seeded_validator_report.json, seeded_field_diff.jsonl,
  new blind package, human review, AI-judge review (v3 frozen),
  field-level promotion report.

## Modules (all unit-tested, no network)
- `evaluation/seed_snapshot.py` — wordsMaster → seed DTO.
- `evaluation/seed_preservation.py` — field classifier + PP/RR.
- `evaluation/seeded_generator.py` — prompt build, Vertex calls,
  deterministic candidate validation, decisions audit call, quota
  ladder + pacing + checkpoint resume (mirrors `resume_356.py`).

## Pilot smoke (3 words, real Vertex) — findings
bottom/adj, refuse/verb, bucket/noun: all artifact_pass=True.

Classification truth (categories, declared actions):
- definition_en: preserved (all 3) — model kept good legacy text.
- examples: `repair` in all 3 — legacy CEFR-keyed dicts with >3
  sentences / inflected targets got conformed to 3 flat examples
  with exact lemma (declared action=replace "converted graded map").
- translations: `changed` — model dropped `؛` separators / added a
  variant, declared + reasons (adjudication decides good vs not).
- mnemonic: bottom & refuse → `regression` with declared
  action=null ("removed mnemonic"); source_type=`null`. bucket →
  `changed` (MSA rewrite, declared improve). These nullifications
  follow the user policy (NULL > bad hook) but drop legacy-valid
  content — flagged for human adjudication, NOT auto-convicted.
- PP 0.29/0.29/0.17 (hard metric: changed-good fields count as
  not-preserved); RR 1.0 (all legacy-defective example pools
  conformed to the v1 standard).

Decision points for the user (gate, not committed):
1. Field-level gate thresholds — none predefined by me.
2. mnemonic nullification adjudication rule (valid legacy content
   dropped with declared null → evidence or vote?).
3. Batch size: full 356 vs further-piloted subset (quota reality).
4. Whether translations separator-normalization is a deterministic
   repair (could promote PP honestly) or stays an LLM change.

## Status
Building. Seed extractor + preservation classifier + generator + config +
smoke pilot done. Next: user review of pilot → field-level promotion
definitions → full-batch or expanded pilot decision.

## Commands
- Tests: `python -m pytest evaluation/test_seed_preservation.py evaluation/test_seeded_generator.py -q`
- Smoke: `.venv-agent/bin/python` + Vertex env (see BT-14 README env).
- Generation: `evaluation/seeded_generator.py` `run_seeded(cfg, identities)`.
## EXP-SEEDED-001A amendment (code + prompt, no re-run)

**Scope:** versioned continuation of the same family. The 3-word v1
smoke artifacts are IMMUTABLE evidence for v1 (a mnemonic_ar/
mnemonic key bug found during review is documented as later analysis,
never overwritten). Golden, v3 judge, and the 241 BT-14 results stay
frozen.

**Prompt:** `evaluation/prompts/lexical_enrichment_seeded_v1.1.txt`
(591 lines, sha256 `fdb8716e1389c86c395429cc1ca81ebd25517e76274c54ebb8887fd8dcc1afb8`).
v1 verbatim + 4 changes only: QUALITY formula replaced by an explicit
superiority sentence; LEGACY PRESERVATION HAS PRIORITY OVER
NULLIFICATION block + CHANGE JUSTIFICATION RULE after #3; MNEMONIC
NULLIFICATION RULE after #11.

**Code (`evaluation/seed_preservation.py`, `seeded_generator.py`):**
- taxonomy += justified_nullification / unjustified_nullification.
  legacy-valid + candidate-null is NEVER direct regression; null
  content -> nullification path, non-null failing value -> regression.
- nullification requires declared action=null + legacy_defect=true +
  concrete evidence (vague preferences rejected structurally);
  unjustified_nullification enters the regression pool.
- replace/improve on non-null legacy requires declared
  replacement_superiority=true + reason, else unjustified_change.
- full declaration contract: legacy_state must match observation;
  declared null must not produce a valid value (else
  field_decision_conflict).
- source_type: llm_improved -> llm_changed; repair ->
  deterministic_repair; nullifications/remain_null -> null.
- pools renamed legacy_valid_pool / legacy_defective_pool
  (deterministic validity, never semantic gold).
- new rates: justified/unjustified change, nullification,
  unjustified nullification, regression (+ counts).
- decision audit prompt requires action/reason/legacy_state/
  legacy_defect/replacement_superiority/evidence per field.

**Status:** implemented + unit-tested (127 passed suite-wide; only
pre-existing infra fixture failure remains). 60-word stratified
pilot pending user approval of strata quotas.

## Pilot-60 draw (EXP-SEEDED-001A, seed 600114)

Sampler: `evaluation/select_pilot60.py` (frozen; tests lock
determinism, quotas, smoke exclusion, floors).
Sample: `output/EXP-SEEDED-001A/pilot60.json`, selection hash
`7ffe5d46e3617c56cf4f040d497100e7b10d4d1926b2b89fc3e9955b15d310dc`.
Composition: POS noun17/verb15/adj12/adv6/function10; CEFR
A1 8/A2 8/B1 9/B2 18/C1 16/C2 1; mnemonic-null 16/16; multi-POS
6/6 (deal, since, spell); technical 9; multi-separator
translations 33; relations-lean 6. Corpus facts constraining the
design: examples contract-pass 0/356 (all legacy sets fail count=3
or exact-token), relations-poor (<2) nonexistent (min total is 2),
multi-POS only 3 lemmas. Function quota 10 (not 7) and noun 17
(not 20) because hard-includes hold 9 function words + since/conj.
Audit overlap (monitoring only, via polysemy stratum, never
forced): since/conj, since/prep, spell/verb. Smoke words excluded.
Run config: `evaluation/configs/seeded_001A_pilot60_config.json`
(v1.1 prompt, 001A output dir). Generation NOT launched (120
Vertex calls pending user go-ahead).

## Pilot-60 Gate report (generation complete, analysis only)

Run: 60/60 success, decisions ok 60/60, zero quota stops, zero
errors. 57 artifact_pass, 3 fail (all `syllables null_forbidden`:
colour/noun, chop/verb, dry/verb — validator forbids null
syllables, but the locked presentation rule keeps monosyllabic
syllabify NULL; chop/dry are monosyllabic so null is arguably
correct, colour needs a closer look; fix proposed, NOT applied).

Pooled (valid pool 381, defective pool 60):
- raw PP 0.638 (243 preserved) | RR 1.0 (60/60 repairs)
- justified change 0.354 (130 changed + 5 justified null)
- unjustified change 0.005 | nullification 0.016
- unjustified nullification 0.003 (1 case) | regression 0.003
- classic regression 0 | unjustified_change category 0
- declaration conflicts 7 total (2 in valid pool; 5 on
  empty-legacy fields are invisible to the pooled rates — known
  reporting gap, documented not fixed).

Case review:
- The 1 unjustified nullification (this/det synonyms): legacy had
  "that" (an antonym, not synonym); candidate emptied the list but
  declared action=replace (not null). Guard fired on the
  declaration/content mismatch — correct behavior; content verdict
  belongs to blind review.
- 5 justified nullifications, all synonyms/hypernym cleanups with
  concrete evidence (spell, elbow, dolphin, chin) + 1 mnemonic
  generic-placeholder removal (round/adv "نفس الرابط." -> null).
- 5 conflicts = audit LLM hallucinating legacy_state=non_null on
  empty antonyms lists (audit noise, caught structurally);
  2 conflicts = declared preserve but collocations changed
  (embryo, medieval).

No 356. Next gate: blind evaluation package (legacy vs seeded
v1.1 arms) + human review + AI judge v3 frozen — pending approval.

## AI-judge run complete (frozen v3, 60/60, terminal 0)

Runner `run_judge60.py` (mirrors resume_356: pacing 4s, 429 ladder,
watchdog, checkpoint, provenance). Rubric ai-rubric-v3 hash
0f7753e5a261, model gemini-3.8-flash, temp 0, thinking low —
UNCHANGED. Decode via adjudication_decode (sole map-touching tool).

AI aggregates (candidate=seeded-v1.1; OPINION only, not quality):
- definition tie50/cand10 | arabic tie46/cand14 | sense
  tie33/cand10/cannot17 | examples tie30/cand29/legacy1 |
  translations cand31/tie23/legacy5/cannot1 | relations cand60 |
  mnemonic tie59/cand1. Legacy wins: translations x5 (0012, 0014,
  0036, 0048, 0051), examples x1 (0023).
- Criticals, all against legacy: target_word_violation 19,
  invalid_relation_synonym 7, example_semantic_error 3. Zero
  against candidate; zero wrong_meaning/misleading/fabricated/cefr.

Human review set (15 blind cards, focus-ordered): 0016 dolphin,
0052 spell-v, 0053 study, 0021 elbow, 0054 this, 0045
reverberate, 0010 chop, 0037 precious, 0020 dry, 0009 chin,
0013 deal-n, 0014 deal-v, 0023 example, 0048 since-conj, 0046
round. Covers: all 6 nullifications, all AI criticals on
relations/examples, all sense-decisive technical cards, all 3
artifact-fails (colour/chop/dry — colour reviewed via gate note),
multi-pos pairs, the single mnemonic-changed+critical card, and
the only examples legacy-win. Translations-only legacy wins
(0012, 0036, 0051) held as add-on request.
Verdicts pending.

## Human-vs-AI comparison (15 cards, decoded, review closed)

Human record: `output/human_review_seeded60/human_judgments_seeded60.json`
(verbatim, incl. 11 example_sense_error + 2 mnemonic_quality_error
as non-v3 classes, held out of the frozen-taxonomy decode;
explicit no-violation conclusions recorded with side null).
Frozen-view decode: `output/human_review_seeded60/decode_analysis.json`.

Human decoded (candidate=seeded): definition tie12/cand3;
arabic tie12/cand3; sense tie8/cand7; examples CAND15/15;
translations tie9/cand5/legacy1; relations cand10/legacy2/tie3;
mnemonic tie13/cand1/legacy1. Frozen criticals all vs legacy:
invalid_relation 6, target_word 7, example_semantic 1. Zero vs
candidate. Sides varied per card (blind held; A=legacy/B=seeded
as a global rule REFUTED).

Agreement: 84/105 = 0.800.
4 flips: 0021 relations human=legacy/AI=candidate (human prefers
legacy's flawed synonyms over seeded emptied list + collocations);
0023 examples human=candidate/AI=legacy (AI's sole examples legacy
win overturned); 0048 translations human=candidate/AI=legacy;
0046 relations human=legacy/AI=candidate (legacy list over
seeded trimmed list + collocations).
11 human-decisive/AI-tie (BT-14 conservatism pattern again:
since x3, round x3, dry x2, chop/chin/this sense+examples).
6 AI-decisive/human-tie (incl. 0014 translations legacy-win,
unopposed).
Criticals overlap on side in every coincident case; class-level
differences only (human sense-flags are non-v3; AI semantic flags
on 0013/0037 where human saw sense issues but no frozen hit).

Gate reading (input, not verdict): no hard-fail trigger (no
identity/schema/provenance/hash failure; the 1 unjustified
nullification is a declaration mismatch with likely-correct
content); no null-regression pattern (5 justified + 0 wrongful);
no seeded semantic-regression pattern (sense 7-0, mnemonic
neutral, technical cards favor candidate except relations-depth
preference on elbow/round). Two substantive cautions: (1)
synonym-nullification leaves inventory holes humans penalize vs
flawed legacy lists; (2) translations legacy-wins (x5 AI) mostly
untested by human (1 tie). Population claims forbidden (15/60,
stress-selected).

## 356 authorization (Pilot-60 Gate PASSED — conditional)

Rationale (methodological, not quality certification): human
agreement 0.800 (84/105) vs 0.524 on the prior stress sample; no
hard-fail; no classic-regression/unjustified-nullification
pattern; seeded clearly ahead on examples + sense in-sample;
criticals 0 vs seeded in both judges.

PRE-REGISTERED doctrine (locked before the run, no code change):
- Relations: Validity > inventory. A correct+useful legacy
  relation is preserved; a wrong/non-sense-aligned one is removed
  even if the list empties. synonyms=[] can be the best outcome
  over a wrong list — not a regression per se. No padding with
  broader relations for inventory coverage.
- Translations: watch field. Record field-level wins/losses as-is;
  any repeated seeded-deterioration pattern goes to later human
  review. The AI judge alone may not declare seeded superior here.

Launch lock: prompt v1.1, rubric v3, model gemini-3.8-flash,
temp 0/thinking low, blind DTO, sampling protocol — ALL UNCHANGED.
The 356 is an evaluation run: no canonical writes, no
auto-promotion at completion. Method earned scale; seeded is NOT
production truth.

## Methodology correction: bulk batch (user ruling, recorded verbatim in substance)

A prior agent claim that batch is "not fit for scale" was
OVERSTATED and is hereby corrected. Facts:
- The Vertex Batch path exists and works: BT-12 ran 1,000
  requests through it with full accounting (356 outputs + 644
  infrastructure-empty). Batch validity was never the issue.
- The real reason bulk batch was not used for the 356 is the
  two-phase dependency (generation -> decision audit built on
  generation output), i.e. orchestration sequencing — not batch
  fitness. resume/retry/cost-log are operational requirements
  buildable atop batch orchestration (BT-12/BT-14 already carry
  provenance/checkpoint/accounting patterns), not grounds for
  rejecting bulk batch.
- The better decision from scratch: Bulk Batch A (seeded
  generation, all words) -> freeze/verify artifact gate ->
  Bulk Batch B (decision audits on A's results). Online path
  reserved for smoke (3-5), probes, debugging, limited emergency
  retries — not hundreds of sequential items. Expected gains:
  far less 429 pressure, better reproducibility.
- Standing: 31/356 generated online (all success) before the
  user stopped the run. Forward transport decision pending
  (continue online vs batch remainder vs full re-batch).

## 356 transport: two-phase Batch Orchestration (user-approved)

Recorded BEFORE any grid job is submitted. Decision: do NOT continue
online for the remaining ~325 (quota fatigue, reproducibility); REUSE
the proven Vertex Batch path (BT-12 did 1000 requests with full
accounting). The 31 online successes are frozen evidence — never
re-picked, never overwritten.

Contract:
- Batch A (generation, remaining identities only): seeded v1.1 prompt,
  temperature 0, NO responseSchema/responseMimeType (parity with the
  online generation call). Gate before B: 1:1 key mapping, parse,
  identity lemma/pos/cefr, deterministic validator, candidate_hash.
  Only artifact_pass items proceed to B.
- Batch B (decision audit): built ONLY from verified A outputs; same
  DECISION_PROMPT, responseMimeType application/json (parity with the
  online decision call), temperature 0. Same seed-preservation
  classification, source_type, nullification evidence contract.
- Provenance: phase=generation|decision + channel=batch on every batch
  line; online 31 lines retain no phase field (combined) — transport
  never enters the evaluation DTO. No canonical writes, no promotion.
- Infrastructure: bucket lexical-enrichment, prefix
  seeded356/exp-seeded-001a-356/, resumable state files per phase,
  idempotent submit guard.

Implementation: evaluation/seeded_batch.py (module) +
evaluation/test_seeded_batch.py (9 unit tests). Status command for
progress readout. Batch A covers exactly the remaining
356 - 31 = 325 identities.

## 356 RUN COMPLETE (two-phase batch, merged) — READOUT

Transport: Batch A generation 325 (online 31 frozen, never re-picked);
job 4605383755215929344 → mapped 325/325, artifact_pass 317, fail 8
(5x syllables null_forbidden monosyllabic, 2x examples_contain_target
multi-token lemma ice cream/line-up, 1x online fourth/adj earlier).
Gate A passed only 317 → Batch B decisions (job 6441726503276249088):
317/317 decisions ok.

Merged evidence in generated_356/ (batch_merge.json):
- provenance 673 lines: online 31 (no phase, combined) + batch
  generation 325 (phase=generation, channel=batch) + batch decision
  317 (phase=decision, channel=batch). Transport never in DTO.
- raw 356 files, progress 356 items.

Decisioned fields (348 identities: 31 online combined + 317 batch):
2784 = 8 fields x 348.
- source_type: legacy_preserved 1420 | llm_changed 879 |
  deterministic_repair 348 (examples, PP=1.0) | null 137.
- justified changed (classify 'changed'): 854.
- watch flags: unjustified_nullification 2 (this/det, fish/noun,
  synonyms), unjustified_change 3 (billion/num collocations +
  definition_en + explanation_ar). Listed for later human spot.
- Watch fields (pre-registered, NOT verdicts):
  translations PP=0.158 (55/348 preserved) — HEAVY change signal;
  synonyms PP=0.451 (157/348) — aligns with relations/inventory
  caution. definition 0.776, mnemonic 0.779, explanation 0.707,
  collocations 0.647, antonyms 0.563.
- raw preserved share 1420/2784 = 0.510 (transport-consistent; pilot
  PP 0.638 was a specific pool definition — not comparable directly).

No canonical writes (0). Input request hashes recorded. Next gate:
blind package + AI judge + human review on the 348 candidate-side
cards as the user next authorizes.

## Official state adopted (user ruling) + next-gate pre-registration

STATE (adopted verbatim by user):
- 356/356 completed formally via Bulk Batch A/B; the 31 online remain
  frozen, never re-run.
- 348/356 have generation + decision complete; the 8 failures are
  RECORDED as failures, not disguised successes.
- 0 canonical writes -> still evaluation, not migration.
- channel=batch lives only in provenance; never in the DTO, cannot
  leak transport identity into blind evaluation.
- deterministic_repair=348 for examples -> PP=1.0 is a contract
  artifact, not standalone evidence of semantic improvement.
- translations PP=0.158 = the strongest current watch signal (many
  changes != regression until blind adjudication).
- synonyms PP=0.451 consistent with validity>inventory; a shorter
  list is not automatically worse.
- this/fish/billion = watch cases, NOT grounds for prompt changes
  before evaluation.

NEXT GATE (pre-registered): Blind package for the 348 -> AI judge v3
-> independent human audit. Watch fields pinned:
  1. translations = primary watch field.
  2. synonyms/relations = primary watch field.
  3. sense_separation = watch conservatism/abstention (seen earlier).
  4. mnemonic = watch flips seen in Pilot-60.
  5. The 5 flagged cases are reviewed, but MUST NOT drive system
     modification before the blind sample result is seen.
Run is LOCKED: next step is blind evaluation, not another generation.

Implementation (new modules, frozen ones untouched):
- evaluation/build_seeded348_package.py: EVAL_ID eval_seeded348_v1,
  SEED 600116, identities deterministically = the 348 decided set,
  same DTO/A-B/assert_blind, transport-leak rejection for
  channel/batch strings.
- evaluation/seeded_judge.py: single-phase Batch judge transport
  (348 cards, rubric ai-rubric-v3 frozen, gemini-3.8-flash temp 0
  thinking low maxOutputTokens 4000 mime json), parse_ballot
  validation, no default-fill, decode via frozen adjudication_decode.

## BLIND EVAL 348 COMPLETE (AI judge v3, batch transport) — READOUT

Package eval_seeded348_v1 (seed 600116): 348 items, candidate sides
A=173/B=175; hashes 57bd1f7a… (package) / 0f478021… (map PRIVATE) /
86b3ea70… (input). Input manifest: 347 success + 1 validator_failed
(fourth/adj, online, kept in eval set per user framing). Transport-key
scan clean; assert_blind clean (channel/noun is a legitimate content
word — false positive avoided, not a leak). Judge batch single-phase
(ai-rubric-v3, gemini-3.8-flash temp 0 thinking low mto 4000):
job 5913327603246170112, 348/348 imported, 0 rejected, 0 malformed,
input_hash 859398ef….

Aggregates (decode_analysis.json, private map):
- field wins (candidate/legacy/tie/cannot-judge):
  definition 50/0/298/- ; arabic 77/0/271/- ;
  sense_separation 59/2/178/109 ; examples 163/19/166/- ;
  translations 169/21/158/- ; relations 345/0/3/- ;
  mnemonic 25/0/323/-.
- criticals (ALL legacy): wrong_meaning 1, misleading_arabic 2,
  invalid_relation_synonym 23, example_semantic_error 14,
  target_word_violation 110. ZERO against candidate across 348.

Watch-field interpretation (pre-registered, AI opinion only):
- translations (primary): candidate 169 vs legacy 21 — no
  deterioration pattern at AI level; PP=0.158-changes are judged
  net-positive by AI. Human confirmation still required before any
  claim (AI alone may NOT declare superiority per pre-registration).
- synonyms/relations (primary): candidate 345/348. Awaiting human.
- sense_separation: 109 cannot-judge (31%) = rubric-v3 abstention,
  expected; legacy won only 2.
- mnemonic: no flip pattern at scale (0 legacy wins; 25 candidate).
- the 5 flagged cases (this, fish, billion x3) untouched; queued for
  human review.

Status: NO system modification from any of this. The 356 evaluation
run is LOCKED. Remaining: independent human audit (user's step or a
stratified sample the user scopes). Canonical writes: 0.

## HUMAN30 STRATIFIED SAMPLE AUTHORIZED + SELECTED (pre-registered)

User ruling: AI-signal is strong but not sufficient alone (sense
109-abstain + known human/AI gap). NO full-348 human review; a
30-card stratified sample suffices, each card reviewed ONCE.
Constraints confirmed: 348 eval artifact LOCKED; no re-run of the
348; prompt/rubric untouched; AI results never treated as gold;
humans = independent adjudication layer; blind A/B (sides stay in
PRIVATE eval_identity_map.json; reviewer pack carries NO AI verdicts
/NO candidate-legacy labels).

Sampling (evaluation/select_human30.py, deterministic, seeded,
drawn AFTER frozen decode): seed 600117.
Strata (30): translations 10 | relations 6 | sense_separation 5 |
examples 4 | definition_arabic 3 | mnemonic 2.
Forced (not drawn): this/det + fish/noun -> relations;
billion/num -> definition_arabic.
Within-stratum guarantees: translations cover candidate AND legacy
AND tie verdicts w/ content-changed priority (cand_changed x4,
legacy x2, tie x4); relations cover emptied + legacy_preserved +
candidate; sense covers multi_pos (deal noun+verb) + abstain;
examples cover candidate + legacy + critical_related; mnemonic
indirect association prioritized (reporter is indirect).

Selected 30 (selection_sha256 c94b47d4…66ac):
translations: call/verb, additionally/adv, age/noun, guarantee/noun,
 citizenship/noun, web/noun (legacy x2), sunlight/noun, import/verb,
 trainer/noun (tie preserved x3), feature/verb (tie changed).
relations: this/det (forced), fish/noun (forced), elbow/noun
 (emptied), settler/noun, my/excl, archbishop/noun.
sense: deal/noun, deal/verb (multi_pos), hierarchy/noun, provoke/verb,
 awareness/noun (abstain x3).
examples: option/noun, ignore/verb, jew/noun (candidate+critical),
 channel/noun (legacy).
definition_arabic: billion/num (forced), fun/noun, congressional/adj.
mnemonic: reporter/noun (indirect), sponge/noun.
Note: deal/noun is multi-POS AND landed in translations (overlapping
 strata are allowed; each card STILL reviewed exactly once).

Artifacts (output/human_review_seeded30/):
 human30_selection.json (operator metadata: keys + tags + strata)
 review_cards_30.md (blind A/B render, no side identity, no AI info)
 human_judgments_30.json (blank ballot template, 30 cards)
Verification: 30 unique ids, counts {10,6,5,4,3,2}, forced present,
 reviewer-facing files clean of candidate/legacy/AI verdict strings;
 unit tests (11) pin quotas/forced/uniqueness/determinism; full
 touched suite 48 passed.

Reconciliation after human ballots (next phase, NOT yet started):
 (1) human-vs-AI polarity: agree/disagree per field on the 30;
 (2) critical-error agreement human vs AI (side + class);
 (3) field-specific agreement (esp. translations/relations/sense);
 (4) semantic-regression verdict: any HUMAN-found candidate-side
     regression in translations/relations/sense = systematic? Then
     STOP promotion + open amendment. Absent regression => candidate
     is a strong promotion candidate, but the SEPARATE migration
     decision still stands. Metrics: agreement >= 0.8 keeps gate
     momentum; systematic regressions halt.

## HUMAN30 REFERENCE JUDGMENTS RECORDED + HUMAN-vs-AI RECONCILE (30)

Reviewer doctrine recorded before entry: judge CONTENT only (not
example count / list length / arm shape); stay CONSERVATIVE on
criticals — turning every small diff into a war crime is how the eval
gets corrupted. The 30 reference judgments are noisy human references,
NOT divinely-placed gold truth.

Two points locked before JSON entry:
1) billion/num is NOT a regression: both arms correct, phrasing-only
   diff; numerals in A do not reduce accuracy.
2) deal/verb critical on A is CONDITIONAL — verified against the full
   record (raw/deal__verb.json): displayed A definition covers
   deal-with + cards only; candidate senses 1 (deal with) and 2
   (cards) also do NOT separate 'deal a blow' => example_sense_error
   on A stands. Not punishing text for info never shown.

Implementation (evaluation/record_human30.py): verbatim side-table =>
blind ballots via adjudicate.record_judgments (contract-validated); 8
non-contract items kept in human30_annotations.json (NOT in the
ballot). Reconcile (evaluation/reconcile_human30.py) maps to
candidate/legacy via PRIVATE map + compares to frozen AI decode.

Bland (whole-card) agreement = 0.6952 (30 cards x 7 fields =
146/210 cells where human status == AI status or both abstain).
Human-vs-AI field agreement:
  definition 26/30, arabic 26/30, mnemonic 26/30 (no candidate-side
  regression; candidate preferred 5/9/2 times),
  translations 19/30, relations 21/30 (AI agreed candidate win but
  human called tie → many "mismatch" are only tie-vs-winner),
  sense_separation 16/30 (+10 abstain: human tie where AI
    cannot-judge — both conservative),
  examples 12/30 (lowest; human more conservative: prefers candidate
    24 vs legacy 6, but flips 6 to legacy when candidate mixed senses).

CRITICALS (all mapped to candidate/legacy via identity map):
  human v3 invalid_relation_synonym x5 — ALL on LEGACY side: this/det
    (that), fish/noun (marine life,seafood), elbow (joint,arm joint),
    archbishop (high priest), sponge (absorber,loofah,wipe).
  AI v3 on sample (15): all vs legacy too (target_word_violation x10,
    invalid_relation_synonym x3, example_semantic_error x2).
  overlap human∩AI (offender side matches): this, sponge.
  human-only (AI missed): fish, archbishop, elbow.
  AI-only (human chose not to flag): item-0010 relations/example,
    item-0071 example_semantic_error (human put on legacy via missing
    sense instead), 10 target_word_violations human did not affirm.
  human NON-v3 (held in annotations, not v3 ballot): deal/noun +
    deal/verb example_sense_error on legacy, provoke mnemonic_quality
    (shared text, attached legacy).

REGRESSION SCAN (human prefers legacy): 7 cells total, 1 watch
(0018 relations legacy) — NOT systematic (needs >=3 watch).
No human-found NEGATIVE-candidate semantic regression. Watch fields
hold: translations 19/30 agree + 0 legacy-preferred; sense 16+10
both-conservative; relations 21/30 + 1 legacy-preferred (0018).

operator arbitration flags (annotations): (a) channel arabic A==B
byte-identical yet arabic recorded A-better; (b) my mnemonic A==B
byte-identical yet mnemonic recorded A-better. Kept verbatim; flagged.

CONCLUSION (pre-registered): translations/relations/sense show NO
systematic candidate regression => DO NOT stop promotion. Candidate is
a strong promotion candidate per the human layer. SEPARATE migration
decision still required (governance lock unchanged). Artifacts:
human_judgments_30.json, human30_annotations.json,
reconcile30.json (000 canonical writes).

## MIGRATION DECISION OPENED (user ruling 2026-09-08)

User ruling: ACCEPT the 348 as Strong Promotion Candidate (reason: the
patterns in the reconciliation — no systematic regression, 0 legacy
wins in definition/translations/mnemonic, Arabic 9–1, relations legacy
critical errors, examples 24–6 despite being the most divergent field,
sense mutual-conservatism, all criticals legacy-side) AND open the
Migration Decision under the exact pre-registered gates G1–G4, zero
canonical writes, migration decision = independent artifact.

Official state: 348 = Strong Promotion Candidate · Migration Decision =
OPEN — ELIGIBLE, NOT WRITTEN · Canonical writes = 0 · Governance lock
= unchanged.

G1–G4 readiness evidence + G3 adoption table + G4 write/rollback plan
were produced read-only (evaluation/export_migration_manifest.py →
output/migration_readiness/migration_manifest_348.json, sha256
`a053dba7…13fa`) and recorded in TICKET 16 (issues/16_migration_readiness.md).
Open items: billion decision provenance (G2), CEFR manual verify on
deal/verb·double/pron·spell/verb (G1), staging dry-run+rollback test
(G4). No experiment, no rerun, no canonical write triggered by this.

## Comments

- 2026-09-08: TICKET 16 CLOSED as READY — ELIGIBLE, NOT WRITTEN (NOT
  EXECUTED). G4 dry-run executed on a WordsMaster staging copy:
  1384 promotion cells applied, audit 1384 rows, rollback restored the
  identical logical state (sha256 pre `56a5a095…81f02` == post-rollback).
  Canonical writes remain 0; governance lock unchanged. See ticket 16.

- 2026-09-08: EXECUTED — 1,384 field-level promotions COMMITTED to
  WordsMaster.db (canonical writes 1). Pre `7a564926…1ffb` → post
  `9c50a5b9…43caa`; audit 1,384; integrity ok; backup
  `WordsMaster_backup_20260908T235840Z.db`. Ticket 16 → EXECUTED.

- 2026-09-08: POST-MIGRATION VERIFICATION PASS + BASELINE FROZEN
  (`Baseline-PostMigration-001`). Confinement proven (0 cells outside manifest);
  observable change 1,189 cells + 195 documented no-op writes (judge tie-leniency
  on verbatim-preserved seeds; zero data impact; equality-guard amendment recorded
  for future waves). Exceptions pack (3 CEFR manual, billion BLOCKED_G2, 8
  legacy-only) + consumer survey in ticket 16. Lock stays ON; no new wave without
  a new governance decision.

(append operator notes below this line; newest at the end)
