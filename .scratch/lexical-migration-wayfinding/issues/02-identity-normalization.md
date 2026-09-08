Type: grilling
Status: resolved

## Question

What is the exact lexical-identity normalization policy: normalization steps, dedupe key (proposed `(lemma, pos)`), and what constitutes an approvable single-word lexical identity?

## Evidence

- `forensic_727.json`: 727 = 121 implausible function-word POS + 571 zero-derivation-mixed + 32 same-lemma-diff-POS + 3 brand-new (`holding`/noun, `complicate`/adj, `dressing`/noun). Method note: initial `(lemma,pos)` overlap used a mis-indexed key and was discarded; counts re-verified with explicit `(wordEn,pos)` sets.
- `forensic_report.md` §2: snapshot mismatch — on-disk WordsMaster (7,300) is not the DB staging imported from (`source_row_id` up to 8,027). Snapshot-identity must resolve before any migration; record how.
- `AGENTS.md`: `id` = stable identity, never recomputed; new word → normalize → dedupe on `(lemma,pos)` → observations → derived rank → CEFR → `difficultyScore` → `unitId`.

## Gate

BLOCKING — resolved by this decision.

## Answer

Canonical lexical identity is keyed by:
(normalized_lemma, canonical_pos).

Normalization folding is deterministic:
1. trim leading/trailing whitespace;
2. lowercase;
3. Unicode NFC normalization;
4. collapse internal whitespace runs to one space;
5. preserve diacritics exactly; never strip them.

Hyphen policy:
- a hyphenated form containing no whitespace is a single-word candidate;
- any form containing whitespace is a multiword candidate and is deferred
  to Ticket 04 for multiword policy.

Apostrophe policy:
- possessive "'s" forms are not independent identities and map to the
  base lemma;
- internal apostrophes are preserved as written;
- punctuation other than permitted internal apostrophes/hyphens makes a
  candidate inadmissible.

Identity is based on the dictionary headword lemma. Inflected surface
forms are not separate lexical identities.

Zero-derivation / cross-POS legitimacy is not decided by Ticket 02.
Candidate POS legitimacy is adjudicated through the canonical POS policy
in Ticket 03.

Proper names and brands are excluded from canonical learner-lexicon
identity.

Abbreviations/acronyms are admissible only when they function as
lexicalized common lexical items and have an approved canonical POS.
Their IELTS matching status is handled separately by Ticket 05.

The dedupe key is therefore:
(normalized_lemma, canonical_pos)

Lexical identity remains separate from frequency, CEFR evidence,
curriculum placement, IELTS evidence, LLM enrichment, and word relations.

The 727 quarantine is evidence/review state, not itself a lexical-identity
definition. No quarantined candidate is automatically promoted without
the applicable review.

The WordsMaster/staging snapshot mismatch remains a migration precondition
and is not resolved by this ticket.

The forensic 727 decomposition 121 + 571 + 32 + 3 remains authoritative
pending reconciliation. The arithmetic discrepancy that 121 + 571 = 692
rather than 695 is carried as an explicit unresolved forensic item; no
value is inferred.
