Type: grilling
Status: resolved

## Question

What is the canonical CEFR evidence precedence: which source wins on conflict, and is curriculum position / difficulty score explicitly barred as CEFR input?

## Evidence

- `AGENTS.md`: legacy `rank`/`frequency 1–6`/`CEFR` provenance unknown → VERIFY, never trust blindly.
- `DECISION_LOG.md` (root): CEFR/rank/frequency trusted source unchosen (pending); IELTS-driven CEFR reassignment REJECTED.
- Draft rule to ratify or amend: never use curriculum position or difficulty score as CEFR; never silently modify authoritative CEFR on LLM disagreement; store CEFR evidence with provenance/version.

## Gate

BLOCKING — ticket 12 waits on this.

## Locked so far (review-approved, not yet a resolution)

- Curriculum position and difficultyScore are barred as CEFR inputs.
  Causal direction is CEFR evidence → downstream difficulty/curriculum,
  never the reverse (legacy difficultyScore already depends on CEFR —
  using it as CEFR input would be circular).
- LLM-proposed CEFR is versioned evidence only; it never silently
  modifies authoritative CEFR and takes effect solely through
  explicit human/QA review.
- Storage model: one canonical CEFR value per identity plus a
  versioned evidence table (source, source_version, value,
  observed_at); conflicts resolve into the canonical value without
  destructive overwrite; history preserved.
- "Legacy default" REJECTED as formulated: unknown provenance cannot
  win by default merely by existing in WordsMaster.

## Open

Which source wins on conflict? RESOLVED per the Answer below: no
undocumented source holds authority; external lexicon selection is an
explicit follow-up decision, not an implicit grant.

## Answer

CEFR is external proficiency evidence and is separate from curriculum
position, difficultyScore, frequency, lexical identity, IELTS evidence,
and LLM enrichment.

curriculum_position and difficultyScore are explicitly barred from setting,
overriding, or inferring canonical CEFR.

LLM-proposed CEFR is evidence-only. It is versioned and cannot silently
modify authoritative CEFR; any effect on canonical CEFR requires explicit
review under the approved precedence policy.

Legacy WordsMaster CEFR values have unknown provenance. They are therefore
preserved as historical evidence and are not granted automatic authority
solely because they exist in the legacy dataset.

Canonical CEFR may be assigned or changed only through an explicit,
versioned CEFR-source precedence policy. The authoritative external CEFR
lexicon/source is not selected by this ticket and remains an explicit
follow-up decision.

CEFR history is preserved in versioned evidence records containing source,
source_version, value, and observed_at. Resolving a conflict changes the
queryable canonical value without destroying prior evidence.

Gate: BLOCKING — resolved subject to the explicit external-source
selection follow-up.
