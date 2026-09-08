# 14: Human linguistic adjudication on the frozen blind package (BT-14)

**What it is:** human verdicts on `output/eval_blind_v1/` (356
items, 7 fields + critical-error checklist each) under the blind
protocol below. The building agent is NOT blind (it can read the
identity map) and therefore MUST NOT render verdicts.

**Blocked by:** 13 (frozen package). Package hashes pinned at
BT-14 opening — package: `965b264a31b377ee`, map:
`d5a4b658b198d24a`, input: `61be6200536fbfeb`. Re-verify before
first judgment; any mismatch ABORTS adjudication (the hash is the
door).

**Status:** PARTIAL / SUFFICIENT FOR METHOD DECISION — closed at
241/356; production judge NOT authorized; post-scale human audit
is the next action.

## Scale-run outcome (method decision, not a full-356 claim)

- 241/356 completed (238 via run_batch + 3 via paced resume run
  AI-356-PACED-v1 before the intentional stop). 0 unresolved.
- Reliability overlap on the shared 20 items = 0.871; conservative
  v3 behavior consistent end-to-end; translations/relations stable;
  no terminal; no blindness leak; quota (429) was the only blocker,
  never a quality failure.
- Remaining 115 unprocessed DUE TO QUOTA, not quality. No claim of
  full 356-item aggregate; the 241 are manifest-order-prefix, not a
  random sample of the 356.
- Rubric: NO amendment indicated.
- Boundary of this gate: it decides whether the AI judge is a valid
  evaluation TOOL (yes, with the documented conservative bias) — it
  does NOT estimate aggregate metrics for all 356 items.
- Paced resume runner + provenance design retained at
  resume_356.py (per-item checkpoint, 4s pacing, 429 exponential
  ladder [15,30,60,120]s + jitter, 10-min no-progress watchdog,
  SIGTERM/SIGINT-safe, quota never recorded as linguistic failure).

## Reliability gate record (conditional PASS, NOT a validation)

- AI↔AI = 0.929 (≥0.80 gate): zero terminal, zero systematic
  critical disagreement, zero leakage, zero contract failures.
- Human↔AI = 18/28 = 0.643: OBSERVED, not a gate failure —
  different metric (human decisiveness vs AI abstention policy).
- Known behavior: conservatism/under-decision (zero polarity
  flips; diffs are Human A/B-better ↔ AI tie/cannot-judge).
- Wording lock: "passed the predefined AI↔AI reliability gate
  and is authorized for 356-item evaluation, with documented
  conservative behavior" — NEVER "AI judge validated".
- Rubric v3 FROZEN for the scale run (no relaxation to chase
  agreement).
- Post-scale human audit (10–15 cards) REQUIRED later; selection
  procedure + seed pre-registered in the scale run record
  (stratified: disagreement-prone fields esp. sense_separation,
  tie-heavy, strongly-decided, polysemy/POS-sensitive) — executed
  AFTER results via the frozen procedure, never cherry-picked.
- Production judge: NOT authorized.

**Spec ref:** spec §7; user step 6 decision framework.

## Execution record
- Package/map/input hashes verified at opening (965b264a… /
  d5a4b658… / 61be6200…) — re-verify before first judgment;
  mismatch aborts.
- New `evaluation/adjudicate.py` (NO map code path — asserted
  by source test): ballot validation, unknown-id refusal, no
  default-filling, judgments file writer.
- New `evaluation/adjudication_decode.py`: SOLE map-touching
  tool; aggregates + private item analysis; runs only after
  judging closes.
- Fixed live: ballot/critical placeholder mismatch between
  blind_package and adjudicate (aligned to dict form) + one
  indentation break from the fix (caught by tests immediately).
- New tests `evaluation/test_adjudication.py`: 5 passed.
  Suite: 159 passed (pre-existing fixture failure deselected,
  unchanged).
- No verdicts rendered. No package rebuild. Promotion
  framework qualitative per step 6 (no invented thresholds).
- Judging page: `output/eval_blind_v1/judge.html` (single
  offline file, no dependencies, no network): file-picker loads
  the package; A/B side-by-side with fixed-height scrolling
  example areas; per-field radios + critical checklist with
  side/evidence + note; progress + prev/next/goto/unjudged-only;
  localStorage persistence; one-click export of
  `bt14_judgments.json` in decode-compatible shape. Verified:
  zero references to the identity map, zero network calls.
  Banner names no filenames (first draft did — fixed).

## Blind protocol (normative)

1. Judge sees ONLY `eval_blind_v1.json` arms A/B + blank ballots.
   The identity map MUST NOT be opened, quoted, or loaded by any
   judging party until judging closes for an item set.
2. Order fixed by eval_id. Batching allowed; skipping forbidden
   (unjudged stays `unjudged`, never default-filled).
3. Per item: 7 field verdicts from {candidate-better,
   legacy-better, tie, cannot-judge} — where "candidate" means
   side X as presented? NO. Verdicts are recorded as
   {A-better, B-better, tie, cannot-judge} (side-relative only).
4. Critical errors recorded per class when observed, with the
   offending side (A/B) and a one-line evidence quote.
5. Validator metrics MUST NOT be shown during judging (no
   execution-compliance contamination of quality scores).
6. Close: decode joins judgments with the map ONCE, producing
   aggregates only (win rates per field, critical counts by
   class/side, tie/cannot-judge rates). Item-level decode stays
   in the private analysis file.

## Decision framework (user step 6, qualitative — no invented thresholds)

- no systematic regression → candidate remains viable
- isolated errors → targeted patch/retest items
- systematic weakness in a field → configuration/prompt/model decision
- unacceptable critical-error rate → NO 1K/production promotion
- The promotion decision is recorded with rationale by a human;
  completion of judging is not acceptance.

## Agent-executable scope (this ticket, now)

- [ ] Package/map/input hashes verified (pinned above)
- [ ] Blindness-enforcing harness: record path with NO map access;
  decode path as the sole map-touching tool
- [ ] Ballot validation + aggregation math tested on fixtures
- [ ] Judgments: HUMAN FUTURE WORK — zero verdicts from the agent
