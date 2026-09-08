Type: grilling
Status: resolved
Blocked by: 05, 08 (both satisfied)

## Question

What is the curriculum placement policy for newly added IELTS vocabulary (stable ID first, then frequency observation, CEFR evidence, IELTS evidence — curriculum position assigned separately and later, never renumbering existing IDs)?

## Evidence

- `AGENTS.md`: `rank != CEFR != unit`; `unitId` is a reassignable curriculum bucket, NOT rank order.
- New identities may only come from approved clean single-word candidates (ticket 05); CEFR from lexicon or flagged-inferred (ticket 08).

## Gate

NON-BLOCKING — resolved. Gates identity creation, not `/to-spec`. Dependencies on 05 and 08 closed at semantic level.

## Answer

Curriculum placement for newly added IELTS vocabulary is pedagogically downstream of lexical identity and evidence.

1. Creation order

For an approved new lexical identity, the canonical creation sequence is:

   1. Pass lexical-identity admissibility under Ticket 02.
   2. Pass canonical-POS requirements under Ticket 03.
   3. Mint a new stable lexical identity ID.
   4. Record source provenance.
   5. Record the versioned frequency observation.
   6. Record CEFR evidence according to Ticket 08.
   7. Attach approved IELTS evidence according to Ticket 05.
   8. Assign curriculum placement last.

Stable identity IDs are permanent and MUST NOT be renumbered because of frequency, CEFR, IELTS, or curriculum changes.

Candidates that fail identity/POS gates do not receive canonical lexical identities merely because they appear in IELTS mapping.

2. Curriculum independence

`unitId` / curriculum position is a reassignable pedagogical bucket.

It MUST NOT be derived mechanically from:

   - lexical rank
   - frequency rank
   - CEFR
   - IELTS presence
   - stable identity ID

The invariants are:

   rank != CEFR != curriculum position
   identity ID != curriculum position

Curriculum placement follows explicit teaching/pedagogical logic.

3. IELTS candidate gate

New IELTS-derived identities may come only from the approved NEW_SINGLE_WORD candidate pool established by Ticket 05.

Each candidate must pass the Ticket 02 identity-admissibility and Ticket 03 canonical-POS gates before identity creation.

IELTS mapping itself MUST NOT create a lexical identity or assign a curriculum unit.

4. Curriculum assignment

Curriculum assignment occurs after canonical identity creation and evidence attachment.

Curriculum assignment is therefore a downstream pedagogical operation, not a side effect of lexical matching or identity minting.

5. Legacy curriculum associations

Legacy unit/curriculum associations are preserved as historical/source evidence under Ticket 10.

They may inform future pedagogical decisions but MUST NOT constrain canonical placement of newly added vocabulary.

Existing identities may be re-bucketed into different curriculum units without changing:

   - stable identity ID
   - lexical identity
   - frequency/rank
   - CEFR evidence
   - IELTS evidence

Curriculum is intentionally revisable while lexical identity remains stable.

6. No automatic placement rule

No rule in this ticket assigns a specific unit based on frequency rank, CEFR, IELTS topic, or any other lexical-data field.

The actual pedagogical placement algorithm remains a separate specification concern.

Gate: RESOLVED / NON-BLOCKING
