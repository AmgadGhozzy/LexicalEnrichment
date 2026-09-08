Type: grilling
Status: resolved

## Question

DifficultyScore final ruling on evidence: KEEP AS DERIVED, REDESIGN, LEGACY ONLY, or REMOVE?

## Evidence

- `forensic_difficulty_v2.json`: formula unchanged (`raw = lo + range × rank_position + pos_delta + syllable_delta; score = clamp(round(raw), lo, hi)`), source `dicPyImp/DifficultyScore.py`.
- Draft findings to verify against the artifact, not assume: legacy rank==id makes the rank component order-position not frequency; ≈29% clamp-flattened; ≈59% stored-score reproduction; staging recomputed scores under an undocumented formula incl. impossible 1s/2s.
- `AGENTS.md`: keep formula as-is; only fix out-of-bounds scores; whether the score adds signal over CEFR+frequency is answered via forensic, not redesign.

## Gate

BLOCKING — resolved as LEGACY ONLY, with redesign deferred behind
a separate evidence/QA gate.

## Answer

The legacy difficultyScore is LEGACY ONLY.

It is not accepted as a measured difficulty score and is not retained as a
canonical derived difficulty value. The historical formula, as executed,
used contaminated/non-authoritative inputs including row-order rank
(rank == id) and CEFR whose provenance is currently unknown. The forensic
analysis also identified clamp-tautology and mixed-process behavior.

Legacy difficultyScore values are therefore preserved untouched as
historical evidence. They are never:
- used as CEFR input,
- used as frequency input,
- used to derive lexical identity,
- used as curriculum truth,
- or presented as a measured learner-difficulty metric.

The staging-recomputed difficultyScore values are rejected outright.
They are not merged, promoted, or treated as alternate evidence because
their computation is not established; the forensic record shows only
partial agreement with the legacy values, non-monotonic behavior, and
values inconsistent with the documented legacy formula.

Any future difficulty score requires a separate gated redesign. A proposed
derived score must recompute transparently from authoritative/versioned
inputs, including real frequency rank and documented syllable handling,
with explicit weights and reproducible provenance.

A redesign must also demonstrate added predictive/informational signal
beyond CEFR and frequency rather than merely re-encoding those variables.
No redesign is approved by this ticket.

Gate: BLOCKING — resolved as LEGACY ONLY, with redesign deferred behind
a separate evidence/QA gate.
