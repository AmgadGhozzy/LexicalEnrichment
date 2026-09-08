Type: grilling
Status: resolved
Blocked by: 02, 03 (both satisfied; 04 satisfied)

## Question

What is the exact IELTS-to-lexical matching policy (ordered match types 1–6) and the required mapping-artifact fields — and do the artifact counts stand as the audited baseline?

## Evidence

- `ielts_mapping.json` (review artifact, NOT migration): `EXACT_LEMMA_POS: 678`, `SAME_LEMMA_DIFFERENT_POS: 34`, `NEW_SINGLE_WORD: 276`, `MULTIWORD: 34`; rules include normalized-exact-first, no blind string UPDATE, duplicate IELTS rows kept as separate evidence rows, `is_ielts` derives from approved mapping only.
- `evaluation/forensic_audit/ielts_missing_words.json`: cleaned missing-candidate list (recompute, don't assume, the ≈270-usable estimate).
- `DECISION_LOG.md` (root): IELTS-as-auxiliary pending; using IELTS to reassign CEFR/rank REJECTED.

## Gate

BLOCKING — resolved. Tickets 09 and 12 unblocked on the 05 side. Final counts come from the artifact, never from draft prose.

## Answer

Lock the IELTS-to-lexical matching cascade in the following deterministic order:

1. NORMALIZED_LEMMA_POS_EXACT
   - Exact normalized lemma + canonical POS match against an approved single-word lexical identity.

2. NORMALIZED_LEMMA_EXACT
   - Exact normalized lemma match where the IELTS row does not provide an exact canonical-POS match.
   - This classification does not authorize creation or modification of a canonical identity.

3. SAME_LEMMA_DIFFERENT_POS
   - The normalized lemma exists in the canonical single-word universe, but the IELTS POS differs from the canonical POS.
   - Canonical POS is governed by Ticket 03 and is never overwritten by IELTS.

4. MULTIWORD
   - The normalized form is a multiword expression under Ticket 02.
   - It is routed to MULTIWORD_QUARANTINE and never mints a single-word identity.

5. NEW_SINGLE_WORD
   - A genuinely new, admissible single-word candidate with no existing lexical identity match.
   - It becomes a candidate only; mapping does not create the identity.

6. UNRESOLVED_MALFORMED
   - Any row that cannot be deterministically classified under the preceding rules.

Each IELTS source row receives exactly one mapping classification.

Matching is performed only against the admissible canonical single-word identity universe established by Tickets 02 and 03. Classification and identity creation are separate operations.

Audited baseline counts:
   - NORMALIZED_LEMMA_POS_EXACT: 678
   - SAME_LEMMA_DIFFERENT_POS: 34
   - NEW_SINGLE_WORD: 276
   - MULTIWORD: 34
   - UNRESOLVED_MALFORMED: 0
   - Total IELTS rows: 1,022

These counts are the frozen audited baseline for the current artifact. A deterministic recomputation is permitted at spec stage after Ticket 02 normalization/folding is fully applied. Any resulting change must come from the mechanical rule application; prose estimates do not override the artifact.

Duplicate IELTS rows across topics remain separate evidence rows. One lexical identity may therefore have multiple IELTS topic associations. Topic rows are never converted into duplicate lexical identities.

IELTS is evidence/discovery only. It MUST NOT overwrite canonical:
   - definition
   - Arabic explanation
   - IPA
   - examples
   - CEFR
   - frequency/rank
   - difficulty
   - curriculum position

IELTS contributes presence, topics, provenance, supporting evidence, and candidate discovery.

The 276 NEW_SINGLE_WORD rows form a gated candidate pool. Each candidate must subsequently pass Ticket 02 identity admissibility and Ticket 03 canonical-POS gates. No candidate automatically creates a lexical identity and no candidate enters a pilot by virtue of appearing in this mapping.

Mapping artifact must preserve sufficient provenance to reconstruct the classification, including the IELTS source row identity, source lemma/form, normalized form, source POS, match classification, matched canonical identity where applicable, and IELTS topic/evidence references. Exact physical DDL is deferred to /to-spec.

Spec-stage verification item (not a blocker): the artifact must use the
#1/#2/#3 classifications consistently — the spec defines precisely what
evidence distinguishes NORMALIZED_LEMMA_EXACT (#2) from
SAME_LEMMA_DIFFERENT_POS (#3) so the two never overlap.

Gate: RESOLVED / BLOCKING
