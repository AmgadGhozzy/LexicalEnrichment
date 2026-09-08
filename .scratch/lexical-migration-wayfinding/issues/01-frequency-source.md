Type: grilling
Status: resolved

## Question

Which frequency source/version/metric is canonical (e.g. `wordfreq` Zipf + version/lang), and what are the exact normalization, ranking-algorithm, and tie-handling rules that derive `lexical_rank` from it?

## Evidence

- `AGENTS.md` field rules: frequency source of truth is `wordfreq` zipf (+ version/lang recorded); legacy `rank`/`frequency 1–6` provenance unknown → VERIFY, never trust blindly.
- `forensic_report.md` §3: `rank == id` for 7,300/7,300 — legacy rank is row identity, not signal. Staging `frequency_rank` same defect (8,027/8,027).
- `DECISION_LOG.md` (root): "مصدر CEFR/rank/frequency موثوق (wordfreq/lexicon) — لم يُختَر" (pending).

## Gate

BLOCKING — resolved by this decision.

## Answer

Canonical frequency source is wordfreq Zipf.

Each frequency observation records, at minimum:
- source = wordfreq
- source_version = pinned wordfreq package version
- language
- metric = zipf
- observed_at

Where the underlying wordfreq corpus/model identity is separately exposed
by the implementation, it is recorded as provenance rather than conflated
with package version.

Canonical lexical_rank is derived deterministically within a pinned
source/version observation set by descending Zipf value.

Ranking uses dense rank:
- equal Zipf observations receive the same lexical_rank;
- normalized_lemma alphabetical order is used only as a deterministic
  presentation/order key within equal-rank groups and never changes the
  rank value.

lexical_rank is a frequency-derived property and is separate from stable
id and curriculum_position.

Legacy WordsMaster rank and frequency (1–6) values are preserved untouched
as historical evidence. They are never consumed as input to new frequency
ranking, never overwritten as canonical frequency observations, and are
not treated as lexical rank.

A new lexical identity receives a new stable id independently of rank.
Its frequency observation is recorded separately, and lexical_rank is
derived from the pinned frequency observations without renumbering
existing ids.

Frequency provenance is versioned; a future wordfreq upgrade produces a
new/versioned observation/rank derivation rather than silently rewriting
historical evidence.
