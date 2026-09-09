# Add-Word Protocol (Ticket 21 — frozen policy)

## Iron rule

```text
lexical_id ≠ frequency_rank ≠ curriculum_position
```

Three independent sequences. The legacy `id == rank` conflation (true for all
7,300 current rows) MUST NOT propagate to any new identity. A new word takes
the next value of an **identity sequence** (e.g. `MAX(id)+1` recorded in the
run manifest, never derived from rank, frequency, or curriculum position).
Rank is always a *derived ordinal recomputed from versioned frequency
observations* — never stored as identity, never `id = rank`.

## Pipeline (in order, each step recorded with provenance)

```text
normalize
  → identity dedupe on (lemma, pos)   [exact + case/space/hyphen fold audit;
  │                                     near-duplicates (no-one/no one class)
  │                                     go to MANUAL REVIEW, never auto-merge]
  → evidence acquisition              [Oxford / IELTS / CEFR observations as
  │                                     evidence_observations rows; unknown =
  │                                     recorded unknown, never defaulted]
  → frequency observation             [wordfreq zipf + version/lang recorded as
  │                                     frequency_source/version/metric]
  → derived rank                      [ordinal from observations; recomputed,
  │                                     never edited in place]
  → CEFR evidence                     [lexicon-sourced, or flagged `inferred`;
  │                                     never trusted blindly from legacy]
  → difficultyScore                   [frozen formula; clamped to CEFR_BOUNDS]
  → enrichment                        [seeded generation ONLY under its own
  │                                     governance ticket; validator gates apply]
  → curriculum assignment             [unitId = curriculum bucket (reassignable),
  │                                     category = topic; unit ≠ CEFR]
  → derived views                     [Oxford/IELTS/CEFR matrices regenerated;
                                        no lexical payload copied]
```

## Candidate additions (NOT canonical words)

The 276 `NEW_SINGLE_WORD` rows in `ielts_mapping_v2.json` are **candidate
additions**. They enter the canonical DB only by passing this protocol under
its own governance decision — never by bulk import, never inferred.

## Stop conditions (any one halts the batch for review)

- identity collision (exact or normalized) that is not a clean multi-POS split
- missing frequency observation with no recorded source
- CEFR assigned without evidence (must be flagged `inferred` or blocked)
- enrichment validator failure (frozen gates; precedent: stand down, report)
- any step proposing `id == rank` (protocol violation by construction)
