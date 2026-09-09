# Ticket 19 — Targeted Remediation (609 cells)

**Status:** EXECUTED — CANDIDATES + EVALUATION + AUDIT COMPLETE — NO CANONICAL WRITES — NO AUTO-TRANSITION (completion report 2026-09-09; promotion is a separate future ticket)
**Opened:** 2026-09-08 (independent ticket; execution ONLY after explicit AUTHORIZE)
**Baseline:** Baseline-PostMigration-001 (unchanged; canonical writes since baseline: 0)
**Parent evidence:** Ticket 18 full-triage map (`output/triage/triage_manifest_7300_v1.json`,
sha `8614274b…05d090`) — the sole source of the 609-cell scope.

## Authorizing context (DECIDED post-18 governance rulings, 2026-09-08)
No full regeneration. The problem is targeted, not dataset-wide.
1. examples → LLM_REVIEW / TARGETED GENERATION (597 cells; per cell: legacy set →
   seeded editor → exactly 3 examples → validator → blind evaluation → promotion
   decision; frozen seeded prompt/config; no prompt re-optimization unless a
   systematic failure appears in this round; KEEP untouched).
2. relations_synonyms → TARGETED LLM REVIEW (6 cells; frozen policy
   `validity > inventory`; an LLM candidate worse/unjustified ⇒ keep legacy;
   LLM_REVIEW is not a change order).
3. relations_antonyms → TARGETED LLM REVIEW (6 cells; same rule; empty antonyms
   are never punished for being empty).
4. definition_en → KEEP (7,300/7,300 passed deterministic triage; no LLM).
5. explanation_ar → KEEP (no LLM).
6. translations → KEEP (no LLM). Doctrine locked: the 348 seeded-review watch
   signal ALONE is not a defect — no triage evidence in the 7,300 justifies
   reopening translations.
7. mnemonic → KEEP (no deterministic repair, no LLM review; stronger than
   expected — zero empty/generic cells population-wide).
8. relations_collocations → KEEP (no LLM).
9. sense_separation → MANUAL ONLY (7,300 defaults + 24 presets stay in the manual
   workflow; never auto-batched to LLM — the AI judge's high abstention field).
10. billion/num → BLOCK (not "solved" inside the round; out of promotion until
    provenance is restored or an explicit governance decision accepts legacy
    evidence).

Scope = 609 LLM-review cells ONLY (597 examples + 6 synonyms + 6 antonyms):
7,324 manual → no generation; 8 blocked → no touch; content KEEP → no touch.

## Requested authorization (candidates ONLY — NOT promotion)
Produce seeded candidates for exactly the 609 manifest LLM_REVIEW records
(examples 597 / synonyms 6 / antonyms 6; identity list = manifest query
`status==LLM_REVIEW`, no other source), with per-cell validation + blind
evaluation + audit trail. Canonical `WordsMaster.db` stays byte-identical.
Promotion to canonical — if any — is a SEPARATE later ticket.

## Explicitly forbidden under this ticket
- Any generation outside the 609 (KEEP / manual / blocked / sense cells).
- Promotion of anything into `WordsMaster.db` (canonical writes: 0).
- Prompt / model / config changes (frozen seeded stack; systematic failure ⇒
  HALT + new decision, never silent tuning).
- Re-running 348/356, re-judging frozen verdicts, touching Ticket 17 rules,
  fixing KNOWN_MICRO_BUG, re-litigating translations-KEEP or any ruling above.

## Acceptance gates (proposal — locked at AUTHORIZE)
1. Input scope byte-exact: 597 + 6 + 6 manifest LLM_REVIEW records; baseline hash
   verified before start.
2. Frozen seeded prompt/config only (hashes recorded per run).
3. examples: exactly 3 candidates per cell; artifact-validator PASS; blind
   evaluation ballots recorded per cell (no schema-pass-as-quality-pass).
4. Relations: `validity > inventory` enforced; empty stays empty unless the
   candidate is strictly justified; worse/unjustified candidate ⇒ keep legacy.
5. Zero touch outside the 609 (KEEP/manual/blocked/sense verified unchanged).
6. Per-cell audit (candidate value, hashes, provenance, validator + ballot refs).
7. NO-OP guard enforced at candidate assembly (mandatory):
   candidate_value == current_value → NO-OP → DO NOT WRITE → DO NOT COUNT AS
   PROMOTION. No-ops counted separately, never inside promotion counts.
8. Canonical DB hash == baseline at close (bytes unchanged).
9. Candidates manifest with SHA-256 (separate artifact; not canonical).
10. Verdict PASS or HALT; HALT on systematic failure with evidence, never tuning.

## Boundary
Success here authorizes NOTHING beyond candidates + evidence. What deserves
writing is decided afterwards, on evidence, in an independent promotion ticket.

## Governance ruling (human-owner, 2026-09-08): AUTHORIZED — EXECUTION MAY BEGIN
- Ticket 19 = APPROVED — TARGETED CANDIDATE GENERATION ONLY. Arithmetic confirmed:
  57,759 KEEP + 609 LLM + 7,324 MANUAL + 8 BLOCK = 65,700.
- Authorized: candidates for the 609 ONLY (examples 597 / synonyms 6 / antonyms 6);
  frozen seeded prompt/config, no prompt optimization; structural+semantic
  validation; blind evaluation per frozen rubric; provenance+hashes+audit;
  batches as needed with full per-request accounting.
- Forbidden: generation outside 609; any WordsMaster.db modification; promotion /
  canonical write; prompt/model/config/rubric changes; re-evaluating 348/356;
  auto-converting MANUAL 7,324 to LLM; touching 8 BLOCKs; out-of-scope
  deterministic repair; overriding any circuit breaker.
- Gates 1–10 as proposed: ADOPTED, with the no-op guard confirmed as a
  PRE-promotion condition (not post-hoc): byte-identical candidate = NO-OP,
  never an improvement — effective whenever promotion is decided, not in 19.
- Boundary: 19 ends at generation → validation → blind evaluation → audit.
  No canonical promotion. After the 609: STOP. No auto Ticket 20.
- Completion discipline required: coverage 609/609, failures, validator results,
  evaluator verdicts, criticals, no-ops, provenance completeness, hashes, any
  quota/circuit-breaker event — before any separate promotion decision.

## Comments

- 2026-09-08 (operator ledger note — scope unaffected, authorized 609 intact):
  reconciled counts from the manifest: content KEEP 57,759 (not 58,368) +
  LLM 609 + MANUAL 7,324 + BLOCK 8 + REPAIR 0 = 65,700. The "58,368 KEEP" figure
  in the decision narrative equals KEEP + LLM lumped (57,759 + 609); the "no
  touch" intent for non-609 cells is preserved verbatim. No figure in the
  authorized scope (597 / 6 / 6) changes.

## Completion report (operator, 2026-09-09) — STOPPED, no transition
Audit: `output/EXP-SEEDED-609/remediation_audit_609.json` (sha `2cc4db8c…1f6e8`).
- Coverage: generation submitted 603 → 603 mapped (590 pass + 13 validator-fail,
  0 API errors); judge attempt-2 submitted 590 → 589 judged + 1 malformed ballot
  (apology/noun). In-scope cells with verdicts: 583 examples + 12 relations = 595;
  unevaluated: 13 no-candidate (validator-failed identities) + 1 no-ballot.
- Validator: 10× syllables-null monosyllabic + 3× contain-target hard lemmas
  (up-to-date, decision-making, yes) — frozen-gate precedent, stood down.
- Evaluator: examples candidate 557 / tie 22 / legacy 4 (leave, duck, cathedral,
  proclaim); relations candidate 6/6 cards. Legacy criticals: target_word 537,
  example_semantic 52, invalid_relation_synonym 34 (incl. all 6 relation cards).
  Candidate criticals: 3, ALL on proclaim/noun (example_semantic_error condemns
  its in-scope examples candidate → REJECTED; definition/arabic ones out-of-scope).
- No-ops: 5 antonym cells byte-identical (judge tie-leniency again) → pre-marked
  DO NOT WRITE; examples 0 byte-identical (structural; 533/597 reuse ≥1 legacy band).
- Provenance: 603 gen lines; judge attempt-1 archived failed + attempt-2 590 + 1
  probe — all accounted. Hashes: snapshot 68ebd3d8 / gen-input cd640122 / prompt
  fdb8716e / package c5df2133 / ballots eb91421e / decode c39228b7. Requests
  submitted total: 1,784 (603 + 590 + 590 + 1).
- Quotas/circuits: none tripped. DB bytes+hash unchanged vs baseline.
- Transport repairs (envelope-only, frozen files untouched, prompt bytes frozen):
  %-escape for 4 seeds; role:user injection after attempt-1 code-3 rejection;
  local name-sort for multi-blob download. Process lesson: unique GCS out-prefix
  per attempt (stale-concat caused phantom 589 rejects; corrected by local re-import).

- 2026-09-08: AUTHORIZED — execution may begin under the ruling above. Operator
  runs generation → validation → blind evaluation → audit for the 609 ONLY,
  then STOPS for the completion report. No promotion path in this ticket.
- 2026-09-09: EXECUTION STARTED. Scope resolved: 609 LLM cells = 603 distinct
  identities (597 examples-only + 6 relation cards(ids 14/64/76/156/5835/6103,
  each needing BOTH synonyms+antonyms; zero overlap with examples set)).
  Seed snapshot `EXP-SEEDED-609/seed_snapshot_609.jsonl`: 603/603 resolved 1:1
  from post-migration WordsMaster.db (sha `68ebd3d8…`). Batch B (decision audit)
  SKIPPED by design: not in the authorized pipeline; triage manifest is the scope
  record and the blind judge compares candidate vs legacy directly.
  Transport note: 4 seeds contain literal `%`, which breaks the frozen
  %-formatter — transport-escaped `%`→`%%` at request build (formatter renders
  `%` back exactly; zero content effect; snapshot bytes untouched). Affected:
  differ/verb, migrate/verb, respectively/adv, theory/noun. Frozen modules
  untouched; new driver `evaluation/seeded609_batch.py` imports frozen functions.
  Batch 609-A SUBMITTED: 603 generation requests, frozen prompt
  (sha `fdb8716e…`, verified identical to 348) / gemini-3.8-flash / temp 0 /
  location global; job `…/batchPredictionJobs/6735170763566874624`;
  input sha `cd640122…`. GCS prefix `seeded609/exp-seeded-609/`.
- 2026-09-09: Batch 609-A SUCCEEDED → imported 603/603 lines mapped: 590
  artifact_pass, 13 validator-fail (0 API errors). Fails: 10× syllables-null
  (monosyllabic: smell/weigh/strike/them/mean/hero/tell/cry/write/bond — same
  frozen null_forbidden tension as 356's 5×) + 3× examples_contain_target
  (up-to-date/adj, decision-making/noun, yes/excl — hard multi-token lemmas,
  same class as 356's ice cream/line-up). Per frozen-gate precedent the 13
  stand down (excluded from judge, reported as generation failures).
  Cell coverage: 596/609 (examples 584/597; relations 12/12 — all 6 relation
  cards passed). Blind package `eval_remed609_v1` (seed 600118): 590 items,
  sides A=317/B=273, blind asserts clean.
- 2026-09-09: Judge batch SUBMITTED: 590 requests (frozen ai-rubric-v3 pins),
  job `…/batchPredictionJobs/4606094039727472640`.
- 2026-09-09: Judge attempt-1 FAILED server-side: 0 judged / 590 rejects, all
  `missing_output` — output envelope carries status code 3
  "Please use a valid role: user, model." Root cause: frozen
  `seeded_judge.build_requests` emits role-less contents; the batch endpoint
  now mandates roles (348 predates this validation; generation requests with
  role:user succeed). Transport-conformance repair (envelope ONLY, prompt bytes
  frozen, frozen module untouched): role:user injected in the 609 judge driver;
  proven first by a single online probe returning a parseable ballot
  (disclosed: 1 probe call). Attempt-1 evidence archived at
  `eval_remed609_v1/judge_batch_attempt1_roleless/`. Judge RESUBMITTED (attempt-2):
  590 requests, job `…/batchPredictionJobs/6683942317805535232`. No frozen-file
  edit; no rubric/prompt/model change.
