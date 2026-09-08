# 01: Gate A — external CEFR source selection (BT-01)

**What to build:** the closed Gate A decision — a named authoritative
external CEFR lexicon/source with pinned version and an explicit
versioned source-precedence order — recorded as a decision that
unblocks canonical CEFR assignment. No code, no migration; a decision
with cited provenance.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Spec ref:** spec §2 (CEFR) + Gate A; wayfinding 08 (legacy CEFR =
evidence, no auto-authority; curriculum/difficulty/LLM barred).

## Decision record (Gate A closed as decision; operational prerequisite open)

- Primary: Cambridge EVP (authoritative for covered lexical senses).
  Exact release/version + access/retrieval date TO BE PINNED at
  license acquisition (OPEN provenance item below) — generic
  "EVP" alone is not a reproducible decision.
- Secondary (corroborating only, never overriding EVP): CEFR-J
  Wordlist v1.6 (2020-03-24, Tono Lab TUFS, attribution required),
  EFLLex (LREC 2018 release, UCLouvain; scientific-use terms).
  Exact retrieved file versions/hashes pinned at acquisition.
- Mechanical precedence: licensed EVP authoritative where it covers
  the sense; CEFR-J/EFLLex corroborate only; legacy CEFR is
  historical evidence only. Where EVP has no applicable evidence,
  no canonical CEFR is inferred from curriculum, difficulty,
  frequency, IELTS, or LLM output — the value stays unresolved
  pending an explicitly approved source policy.
- Operational prerequisite (not optional cleanup): required EVP
  license/access must be acquired and provenance-pinned before any
  canonical EVP-based CEFR assignment runs. Lack of access blocks
  execution; it never triggers silent fallback.
- Record minimum (per review): source name, exact version/release,
  retrieval/provenance reference, CEFR value representation,
  explicit precedence order, effective date/version of decision.

- [ ] Authoritative external CEFR source named with exact version
- [ ] Precedence order over versioned evidence written explicitly
- [ ] Legacy-CEFR handling under the new policy stated (evidence stays)
- [ ] Decision recorded; BT-10 CEFR-stratum OPEN note cleared or restated
- [ ] Record states at minimum: source name, exact version/release,
  retrieval/provenance reference, CEFR value representation,
  explicit precedence order against other CEFR evidence, and
  effective date/version of the decision (no generic source names)
- [ ] No other ticket's scope changed by this decision
