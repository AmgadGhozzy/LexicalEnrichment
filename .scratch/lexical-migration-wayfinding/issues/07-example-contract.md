Type: grilling
Status: resolved

## Question

What is the exact canonical example count and contract (exact-lemma-token rule, sense alignment, CEFR-appropriateness policy explicitly NOT length-based, validation rules, regeneration scope)?

## Evidence

- `legacy_examples_pass_sample100.json` + `legacy_examples_fail_sample100.json`: quality baseline samples (structural pass ≠ quality).
- `AGENTS.md`: legacy `FinalClean.classify_examples` mapped CEFR by sentence word-count (wrong); 14.8% of 43,800 cells fail exact-lemma check; baseline 3 high-quality examples, 4th/5th only if polysemy needs it.
- Draft baseline: 3 examples with 11 requirements; needs lock, not assumption.

## Gate

BLOCKING — resolved. Regeneration design and pilot scope unblocked.

## Answer

Canonical examples are defined per lexical identity.

1. Example count
   - Default: exactly 3 canonical examples per identity.
   - A 4th or 5th example is permitted only when genuine polysemy/sense coverage requires it.
   - Additional examples are never default padding and must provide distinct pedagogical value.
   - The legacy six-cell CEFR example grid is not part of the canonical contract.

2. Exact-target requirement
   - Every canonical example MUST contain the identity's exact normalized lemma as a standalone token.
   - Inflected forms, derived forms, synonyms, related forms, or substitutes do not satisfy the requirement.
   - No exceptions.

3. Semantic contract
   - Each example MUST match the identity's canonical POS and intended lexical sense.
   - Examples must be grammatical, natural English appropriate to the learner context, and provide contextual variation.
   - Polysemy extras must correspond to genuinely distinct senses rather than superficial wording variation.

4. CEFR appropriateness
   - Sentence word count/length MUST NOT be used as a CEFR certification rule.
   - Length may be retained as a diagnostic feature only.
   - CEFR appropriateness is evaluated from lexical, grammatical, semantic, and learner-level fit and remains subject to human quality review.

5. Regeneration and preservation
   - Canonical examples are fully regenerated under this contract.
   - The existing 43,800 legacy example cells remain preserved unchanged as historical/source data.
   - No sentence-by-sentence repair of the legacy grid is required.

6. Validation
   - Structural validation MUST verify exact-target presence, POS/sense compatibility where machine-checkable, absence of placeholders/metadata leakage, and schema compliance.
   - Structural compliance is not a quality pass.
   - Naturalness, contextual usefulness, sense fit, and CEFR appropriateness require quality evaluation/human gating.

Gate: RESOLVED / BLOCKING
