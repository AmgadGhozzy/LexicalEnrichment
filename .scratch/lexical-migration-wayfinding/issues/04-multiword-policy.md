Type: grilling
Status: resolved
Blocked by: 02 (satisfied)

## Question

What is the multiword policy: how are multiword expressions (e.g. `solar system`, `look back`) represented — and until a multiword architecture is approved, is `MULTIWORD_QUARANTINE` with preserved evidence the ruling?

## Evidence

- `ielts_mapping.json`: `MULTIWORD: 34`, "multiwords excluded from lexical identity, pending phrase policy".
- Draft proposed `MULTIWORD_QUARANTINE`; needs explicit approval, not silent adoption.

## Gate

RESOLVED / NON-BLOCKING — policy locked; physical DDL downstream of `/to-spec`.

## Answer

Adopt MULTIWORD_QUARANTINE as the canonical policy for multiword expressions until a dedicated multiword architecture is explicitly approved.

1. Identity boundary
   - Any normalized lexical form containing internal whitespace is excluded from the single-word lexical_identity layer.
   - No canonical single-word identity may be minted from the phrase.
   - A multiword expression is treated as an atomic quarantined expression, not as a collection of single-word identities.

2. Quarantine preservation
   - Every quarantined expression MUST preserve:
     - original source form
     - normalized form
     - source/provenance information
     - classification
     - quarantine status
   - Exact physical DDL is deferred to /to-spec.

3. IELTS multiwords
   - The 34 IELTS multiword entries remain represented in the mapping artifact.
   - They are classified as MULTIWORD_QUARANTINE and retain their IELTS evidence, including associated topics.
   - They are counted and preserved; no lexical identity is minted from them.

4. Component prohibition
   - A multiword expression MUST NOT be split into pseudo-single-word identities.
   - Example: "solar system" must not cause the phrase itself to mint a "solar" or "system" identity as a consequence of processing the phrase.
   - Component POS values MUST NOT be assigned to the phrase as its canonical POS.

5. Future architecture
   - A dedicated multiword representation may be designed later as a separate architectural decision.
   - Until that decision is approved, quarantine is the authoritative handling state.

Important distinction:
   - MULTIWORD_QUARANTINE is a preservation/classification state, not a canonical lexical identity.
   - A technical quarantine-record identifier may exist for traceability, but it MUST NOT be treated as a lexical_identity identifier.

Gate: RESOLVED / NON-BLOCKING
