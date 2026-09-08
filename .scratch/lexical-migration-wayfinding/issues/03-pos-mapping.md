Type: grilling
Status: resolved

## Question

What is the authoritative POS normalization mapping between IELTS POS tags and canonical POS?

## Evidence

- `ielts_mapping.json` rules: "POS-aware verification, no blind string UPDATE"; counts `EXACT_LEMMA_POS: 678`, `SAME_LEMMA_DIFFERENT_POS: 34`.
- `forensic_727.json`: 121 confirmed POS distortions among staging extras (`the`/`and`/`would`/`shall`→noun, `vice`/`well-being`→verb suspects).
- `AGENTS.md`: 727 extras UNPROVEN — required match report `X=exact lemma+POS / Y=same lemma diff POS / Z=genuinely new / W=malformed` before any quarantine/delete decision; do NOT re-litigate, decide the mapping.

## Gate

BLOCKING — resolved by this decision. Ticket 05 unblocked on the 02+03 side.

## Answer

Canonical POS inventory is locked to the 11-tag enum:
adj, adv, conj, det, excl, modal, noun, num, prep, pron, verb —
as enumerated in `evaluation/prompts/schemas/lexical_output.v1.json`
(identical enum carried in `lexical_output.v1.1-candidate.json`).
No tag may be added, removed, or renamed without a superseding decision.

One identity carries exactly one canonical POS, per the Ticket 02 key
`(normalized_lemma, canonical_pos)`. A lemma with several legitimate
POS values yields separate identity records (e.g. `get`+verb and
`get`+noun are distinct identities if each POS is adjudicated
legitimate). Composite values such as `noun+verb` or `adj+prep` are
not canonical POS values; where observed in staging they are source
anomalies held as review evidence, never stored on an identity.

IELTS POS maps 1:1 by name onto canonical POS:

| IELTS | Canonical |
| ----- | --------- |
| noun  | noun      |
| adj   | adj       |
| verb  | verb      |
| adv   | adv       |

The other seven canonical tags (conj, det, excl, modal, num, prep,
pron) are unsourced from IELTS and are never inferred from it.
IELTS evidence cannot mint a canonical POS, and no canonical POS is
inferred from a word's meaning or translation merely because IELTS
lacks a fitting tag.

Zero-derivation / cross-POS legitimacy is adjudicated per item by
human review. The forensic `defensible` vs `wrong` lists (e.g.
`torture`/noun vs `get`/noun) are starting evidence, not verdicts.

Closed-class → open-class POS mismatches are presumptively malformed
and require explicit cited evidence for approval. The presumption is
rebuttable on a per-item basis; it is never a blanket rejection rule.

The 121-case forensic classification is review evidence and default
suspicion, not a canonical POS dictionary and not a business rule.

Ordering is source POS → canonical POS → identity, never
IELTS POS → identity. `ielts_mapping.json` remains a review artifact,
not an authoritative mapping table in itself.
