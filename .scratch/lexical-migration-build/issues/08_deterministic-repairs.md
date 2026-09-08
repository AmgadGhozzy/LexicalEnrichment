# 08: Deterministic repairs + CI guard (BT-09)

**What to build:** the settled deterministic repairs with
before/after counts (UK-IPA fallback with `fallback_from_us`
provenance, never LLM; grounding-artifact removal incl. the two
known leaks) plus the CI/validation guard rejecting URLs,
grounding markers, and citation artifacts in learner-facing
fields — all verified through the staging-audit seam.

**Blocked by:** 07 (evidence/quarantine schemas).

**Status:** resolved

**Spec ref:** spec §4 (legacy enrichment handling), §6; AGENTS.md
IPA + syllabification rules (NULLs preserved, no LLM).

## Implementation record

- New module `evaluation/deterministic_repairs.py` (pure strings;
  no I/O, no DB, no LLM): `uk_ipa_fallback` (dictionary /
  fallback_from_us / missing with provenance, no slashes
  introduced), `strip_grounding_artifacts` (URLs, 【】 segments,
  daggers; whitespace-collapsed; Arabic/IPA/CJK byte-preserved in
  test), `ci_guard_learner_text` (url / bracket_citation / dagger
  / bare_citation defect codes; quality and emptiness out of its
  jurisdiction), `apply_ipa_fallback` + `apply_artifact_strip`
  (before/after counts, inputs never mutated).
- New tests `evaluation/test_deterministic_repairs.py`: 13 passed
  (provenance branches, contamination removal, script
  preservation, guard flags and clean passes, exact counts,
  non-mutation).
- Suite: 89 passed (new + all prior). Pre-existing
  `test_input_builder_determinism` failure unchanged (missing
  fixture), out of scope.
- Scope held: transformations + guard locked on fixtures. No
  application to real data rows in this ticket (execution scope).

- [ ] Before/after counts published for every transformation
- [ ] UK fallback provenance distinguished (fallback vs dictionary)
- [ ] Monosyllabic NULL syllabification preserved; nothing invented
- [ ] CI guard rejects contaminations; suite green
