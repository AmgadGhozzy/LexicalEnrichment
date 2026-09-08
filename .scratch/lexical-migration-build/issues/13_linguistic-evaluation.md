# 13: Blind linguistic evaluation package for the 354 (BT-13)

**What to build:** a frozen blind A/B evaluation package over the
354 ok/partial pilot outputs vs legacy comparator content — with
identifiers stripped, sides randomized under seed, identity map
kept separately, per-field ballots + critical-error checklist.
Human judging itself is future work; this ticket delivers the
frozen package + forms, never verdicts.

**Blocked by:** 12 (pilot outputs) — inputs frozen, no regen.

**Status:** partial — package frozen, ballots blank, judging NOT
started. No verdicts rendered by this ticket.

**Spec ref:** spec §7 (blind human evaluation, equalized review);
wayfinding 07 (structural ≠ quality).

## Execution record

- New module `evaluation/blind_package.py` (no DB inside; legacy
  rows are caller-supplied ro input): DTO equalization (same arm
  shape; CEFR level keys stripped both sides), seeded A/B
  randomization, separate identity map, blank 7-field ballots +
  7-class critical-error checklist, frozen eval input with hash.
- Leak discipline learned twice live: bare-word bans
  false-positive on real content ("TV pilot", "thinking").
  Final rule bans IDENTIFIER SHAPES only (regex: candidate keys,
  run ids, EXP ids, model ids, exact versions, long hex,
  manifest/provenance field names) and scans blinded content
  only — with a regression test proving content words pass.
- Frozen `output/eval_blind_v1/`: 356 items
  (`eval_blind_v1.json`), sides A167/B189, PRIVATE
  `eval_identity_map.json` (never bundled with the package),
  `eval_input.json` (hash bf7a1479…).
- Comparator: ro legacy rows for the 356 ids (single pass).
  No judging, no regeneration, no canonical writes.
- New tests `evaluation/test_blind_package.py`: 7 passed.
  Suite: 153 passed. Pre-existing fixture failure unchanged.

- [ ] Eval input frozen (354 ids + output hashes + run refs)
- [ ] DTO equalized: same shape both arms, no identifiers, no
  count/CEFR-level clues, sides seeded-random, map separate
- [ ] Per-field ballots (7 fields) + critical-error checklist (7 classes)
- [ ] No judging, no regeneration, no canonical writes
