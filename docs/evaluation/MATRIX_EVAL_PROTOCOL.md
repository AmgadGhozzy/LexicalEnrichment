# Matrix Evaluation Protocol — PILOT-15-V1 / MATRIX-15-V1

**Status**: FROZEN GOVERNANCE for the run. Date: 2026-09-03.
**Not to be tuned after outputs are collected.** Any change after first batch = a V2 experiment, not a fix.

This protocol governs the human blind evaluation of the 9-cell matrix over the fixed 15-word pilot.
It is read-only for the duration of PILOT-15-V1. It must not be modified after generation begins.

---

## 0. Frozen artifacts (do not edit during the run)

| Artifact | Location | Rule |
|:--|:--|:--|
| PILOT-15-V1 | `evaluation/experiments/15_word_matrix/pilot_manifest.json` | FROZEN |
| MATRIX-15-V1 | `evaluation/experiments/15_word_matrix/matrix_manifest.json` | FROZEN |
| Prompt v2.1.0 | `evaluation/prompts/lexical_enrichment_final.txt` | FROZEN (hashes recorded in each run manifest) |
| Schema (experimental) | `evaluation/prompts/schemas/lexical_output.v1.json` | FROZEN as EXPERIMENTAL input, NOT canonical |
| Old baseline | `golden_set/golden_v2.json` | IMMUTABLE |

---

## 1. Selection bias (null discipline cannot be judged here)

- 14/160 golden entries carry legitimate null core fields (`mnemonic_ar` for no-hook words, `word_family` for function words) and were excluded.
- **Therefore PILOT-15-V1 evaluates enrichment quality on non-null-capable entries ONLY.**
- This pilot **cannot and does not** validate null-generation behavior or the null-default rule.
- The selection is biased toward configs that produce *more* content (esp. mnemonics). A config with disciplined nulls will not be fairly rewarded here.
- Null-capable words MUST be re-introduced in the 100-word pilot before any conclusion about null discipline.

---

## 2. Baseline metadata errors are NOT quality signals

- The Old Version baseline has 6 known POS data errors (`thank`, `paper`, `loud`, `dial`, `stir`, `blend`). Their presence in the baseline is a **metadata/data error**, not a reflection on candidate quality.
- `BASELINE ERROR?` on the scoring sheet is a **metadata flag only** — it is neither a penalty nor a bonus to any candidate's quality score.
- A candidate that improves on a wrong baseline may be factually correct (equal quality) — never infer "better model" from a baseline correction.
- Baseline corrections are tracked in a **separate result track** (`pos_corrections` in the pilot manifest), never folded into content-quality scoring.

---

## 3. Two correctness tracks (kept separate)

1. **Corrected-POS track** — score the generated output against the CORRECTED POS for the whole entry (definition, senses, examples must match the true POS).
2. **Baseline-consistency track** — compare the Old Version against its own (immutable, possibly-wrong) baseline POS, solely to document the data error.

These are separate. Do not average them together.

---

## 4. Evaluation rounds

### Round 1 — every candidate vs Old (blind, randomized)
- Each of the 9 candidates is independently compared against the Old Version.
- Labels are randomized: `Version 1..9` + `Old` with NO model / temperature / thinking / grounding / prompt identity visible.
- Order of words and candidates is shuffled per evaluator / per session.
- Output: per-field scores for Old and each candidate + `BASELINE ERROR?` flag.

### Round 2 — top candidates head-to-head (blind, randomized)
- Only the top 2–3 candidates (by Round 1 field-level scores, NOT by vague preference) advance.
- They are compared directly against each other, labels re-randomized.
- Round 2 decides the final ranking among the leaders.

---

## 5. Field-level scoring (no single "vibe score")

Each word, each candidate, each field scored independently on 0–5 (or N/A):

| Field | Score |
|:--|:--|
| Definition EN | 0–5 |
| Explanation AR | 0–5 |
| Senses | 0–5 |
| Examples | 0–5 |
| Pronunciation | 0–5 |
| Mnemonic | 0–5 / N/A |
| Word family | 0–5 / N/A |
| Collocations | 0–5 |
| Synonyms/Antonyms | 0–5 |
| Translations | 0–5 |

Plus, per entry: `CRITICAL ERROR? YES/NO`, `BASELINE ERROR? YES/NO`, `PREFERRED VERSION (A..I or Old)`.

Never collapse to a single average as the *only* verdict — retain these per-field signals.

---

## 6. Critical errors tracked separately

- `CRITICAL ERROR?` is recorded independently of ordinary quality scores.
- Examples: factually wrong definition, wrong pronunciation IPA, a fabricated sense/translation, a hallucinated lexical fact, malformed/duplicated `sense_no`, an example that omits the exact target lemma.
- A candidate with any critical error is not a winner even if its average is highest.

---

## 7. Winner hierarchy

Winner is chosen by this well-ordering, NOT by raw average:

```
Accuracy (critical errors, factual correctness)
  > overall learner quality
  > Arabic quality
  > semantic / sense quality
  > pedagogy (mnemonic, examples, relations)
  > cost / latency
```

- Do not let Round-1 "beats Old" become the sole criterion — a candidate can beat a flawed Old while being objectively wrong. Field-level accuracy + critical-error track stay authoritative.
- Cost/latency only breaks ties after quality: e.g. Pro at ~4× cost for <1% quality gain → Flash wins; Pro clearly cutting sense/pronunciation errors → Pro justified.

---

## 8. Grounding interpretation

- **Flash** `t02_low_off` vs `t02_low_search` differ only in grounding → this is the ONLY clean grounding comparison in the matrix.
- **Pro** `high+search` is a **composite** configuration; do not attribute its result to grounding alone.
- **URL Context is NOT tested** in this matrix. It becomes a follow-up (3–5 cells: best_config / best+Search / best+URL / best+Search+URL) only if Search demonstrates sufficient value.

---

## 9. Schema is experimental

- `lexical_output.v1` is an **experimental input**, fixed across all cells to minimize variables.
- It **cannot** be declared production-canonical from this experiment.
- Schema validation/selection is a separate gate (`EXP-015-schema`) run AFTER the best generation configuration is chosen: coverage, no hallucinated fields, correct null support, exactly-3 examples, no additional properties, sense representation, DB fit.

---

## 10. Scale-up gating (15 → 100 → 1000)

- **15-word matrix** → picks best generation config (this run).
- **100-word validation pilot is MANDATORY** before any 1000-word production run.
- Rationale: the 100-word pilot re-introduces null-capable entries, surfaces distribution-level failures the 15 cannot, and validates the frozen config at scale.
- Only a clean 100-word pilot unlocks 1000-word production batches.

---

## 11. Freeze / anti-move-the-goalposts rule

Once batch generation starts:
- No edits to the 15 IDs, the matrix cells, the prompt, the schema, or the old baseline.
- No rubric tuning after seeing outputs.
- Any modification = a new V2 experiment with its own manifests.

No experiment is meaningful if we cannot say exactly what changed between runs.
