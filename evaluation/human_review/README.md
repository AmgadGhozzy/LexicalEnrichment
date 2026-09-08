# Human Blind Review

Generate self-contained, **blind** human-review HTML artifacts to compare lexical
enrichment candidates (e.g. `golden_v2` baseline vs an experiment run) without
revealing which candidate came from which source.

## Layout

```
evaluation/human_review/
├── generate_blind_review.py   # builds review.html + manifest.json + responses.json
├── review_template.html       # static single-page template (no backend/API/internet)
├── README.md
└── reviews/
    └── HR-2026-09-03-001/
        ├── review.html        # reviewer opens THIS (pure, no source identity)
        ├── manifest.json      # identity map — KEEP PRIVATE, do NOT give to reviewer
        └── responses.json     # field-level judgments (filled/exported from the page)
```

## Blindness protocol (strict)

- `review.html` contains **zero** source identifiers: no `golden`, `exp-002`, `v2.2.0`,
  `v2.2.1`, `OLD`, `NEW`, or `EXP-` tokens — not in values, not in HTML comments,
  not in `data-*` attributes. Option A/B order is randomized deterministically.
- **Only** `manifest.json` holds the identity map (`word_id -> a/b` source). The
  reviewer must never receive it.
- After a review, `responses.json` (blind judgments) is decoded against `manifest.json`
  to produce the analysis.

## Generate a review (4 contested words)

```bash
python generate_blind_review.py \
  --words election independent puzzle gastric \
  --seed 20260903 \
  --review-id HR-2026-09-03-001
```

Output:
- `reviews/HR-2026-09-03-001/review.html` — open in a browser, judge A vs B per field,
  then click **Save / Export responses.json** (fully offline).
- `reviews/HR-2026-09-03-001/manifest.json` — identity map (private).
- `reviews/HR-2026-09-03-001/responses.json` — skeleton + filled judgments.

## Later: larger subset (e.g. 100-word)

```bash
python generate_blind_review.py --words-file words.txt --seed <SEED> --review-id HR-XXX
```

## Review criteria shown per word

- **Examples** — "Which option has better examples?" judged as a **whole set**:
  naturalness, correctness, target-word usage, contextual usefulness, learner value.
- **Mnemonic** — which hook is better (or whether null was justified).
- **Critical error?** — wrong POS, wrong primary sense, invented pronunciation,
  incorrect translation, circular definition, inflection/plural instead of exact
  lemma in an example, invalid relation, hallucinated / misleading mnemonic,
  unjustified null.
- **Is the difference meaningful?** — yes vs no / likely noise.
- **Notes** — free text.

## Schema-neutral / blind rendering protocol

- Every option is rendered from the **same normalized DTO**
  (`definition / arabic / examples / mnemonic`) with identical containers, headings,
  and typography — no senses-array asymmetry, no source-specific structure.
- CEFR labels are **not shown** (so the test is quality of content, not who wrote
  more proficiency bands).
- **Equalized Full-Set Review**: all examples are shown for every option, but inside
  a **fixed-height scrollable container** with **no counter, count, or pagination
  indicator** — the reviewer cannot tell how many examples each option has.
  Example order is preserved from each candidate (not shuffled).
- `example_count` per candidate is recorded **only** in `manifest.json` (outside the
  blind artifact) for post-review analytics — never shown to the reviewer.

## Deriving metrics from responses.json

Once decoded against the manifest, per-field win rates can be computed:
example win rate, mnemonic win rate, critical-error rate (per candidate),
meaningful-difference rate, tie rate.
