# 12: Pilot execution — regen, validation, eval prep (BT-11)

**What to build:** the executed pilot: canonical example
regeneration under the 07 contract on v2.2.3 (experimental
candidate only) with full LLM-versioning capture, automated
validation through the validator + staging-audit seams, and the
blind human-evaluation package per the locked equalized-review
design — reported as experiment evidence, never a
production-readiness claim.

**Blocked by:** 08 (repairs), 11 (manifest), 05 (LLM versioning).

**Status:** partial — 1,000/1,000 accounted; 356 processed;
644 held; probe done (batch-specific). NOT resolved.

**Final accounting (locked): 354 + 2 + 644 = 1,000.**

- 354 successful execution: real payload + all structural
  gates green. Execution success ONLY — no quality claim.
- 2 partial / identity-validation limitation (`ice cream`,
  `line-up`): real contract failures on multiword/hyphen
  identity forms — not linguistic failure, not infrastructure
  failure, not harmless. Validator NOT adjusted to beautify
  the scoreboard. Provenance retained.
- 644 infrastructure-empty: `{}` + uniform job-level code-13
  error. NO linguistic, model, or validator attribution.
  Distribution shows no content/CEFR/POS clustering, which
  SUPPORTS (not mathematically proves) the batch-level/
  infrastructure hypothesis over a linguistic one.
- NULL behavior is descriptive evidence only: mnemonic null
  15/356, phonetic_uk null 188/356 prove transport no longer
  forces fabrication. Null compliance ≠ mnemonic quality.
- Diagnostic probe RUN-PROBE-1 (separate history, own
  provenance): 3/3 previously-failed entries succeed direct
  with zero validator failures → batch-path-specific failure
  highly likely. Probe was diagnosis, never a retry. NO blind
  batch retry executed or authorized.
- Linguistic quality (definitions, Arabic, senses, examples,
  translations, relations, mnemonics) UNASSESSED — requires
  the blind evaluation layer, with quality separated from
  execution compliance.
- Canonical state: 0 migration, 0 canonical writes, Golden
  frozen, 7,300 untouched, 8,027/727/34 quarantined.
  Completion is not acceptance; no promotion authorized.

**Spec ref:** spec §4 (examples, LLM status), §7 (pilot,
evaluation); wayfinding 06 (difficulty untouched), 07, 11.

## Full-run record (RUN-BATCH-1, batch job ...3053884887493771264)

- Input: frozen manifest verified (hash recompute match, file SHA
  pinned bb7932e5…); 1,000-line JSONL built by
  `evaluation/pilot_batch.py` (frozen-sample intactness asserted;
  config fingerprint 672fe52d…); exact v2.2.3, no mid-run change.
- Terminal accounting: 1,000/1,000 lines present.
- 356 MODEL_TEXT payloads processed (`pilot_batch_process.py`,
  4 tests): 354 ok + 2 partial, all with BT-05 history rows
  (356, RUN-BATCH-1, job pinned), output-hash verified,
  guard defects 0.
- Validator failures by code: TARGET_WORD_MISSING × 2 —
  `ice cream` (multiword lemma living in the master baseline)
  and `line-up` (hyphenated): exact-token edge cases the
  validator correctly caught, NOT pipeline breakage. Flagged
  for identity-layer attention (02 whitespace rule vs legacy
  master contents).
- 644 rows: EMPTY `{}` responses, zero evaluable bytes.
  Single uniform class: job-level code-13
  (Static policy config / quota). NO linguistic, model, or
  validator attribution possible or attempted. NO batch retry
  executed (bound 7: systematic failure → stop, don't burn).
- Diagnostic probe (separate run RUN-PROBE-1, own history, 3/3):
  previously-failed ids 5985/2012/1665 all succeed via the
  direct path with ZERO validator failures → batch-specific
  failure highly likely; 644 stay HELD pending batch-failure
  understanding. Probe is diagnosis, not a silent retry.
- Accurate rate statement: valid model payloads 356/1,000
  (35.6%); 644/1,000 (64.4%) empty payloads under a uniform
  infrastructure/policy error. "Model failure rate" NOT claimed.
- Zero canonical writes. Raw batch output immutable. Frozen
  inputs byte-untouched. Suite: 146 passed (pre-existing
  fixture failure unchanged).
- NOT done: 644-entry recovery (needs batch-failure root cause
  + separately authorized retry with own provenance); blind
  human-eval package on the 356 (evaluation layer, next scope).

**Spec ref:** spec §4 (examples, LLM status), §7 (pilot,
evaluation); wayfinding 06 (difficulty untouched), 07, 11.

## Amendment record (nullable transport alignment)

- Root cause (found, not guessed): the v1.1-candidate schema
  file ALREADY carried `"nullable": true` on phonetic_uk +
  mnemonic_ar (top + sense level), and `convert_gemini_schema`
  already translated it — but `validate_schema` validated
  against the RAW schema, bypassing its own converter. Contract
  defect in the seam, not model output, not lexical semantics.
- Fix in `evaluation/lexical_validator.py` ONLY (no schema-file
  change, no semantics change): `validate_schema` converts via
  `convert_gemini_schema` at entry; converter made idempotent
  (re-conversion keeps a single "null" member instead of nesting
  unions), so the pre-converted `artifact_validator.main` path
  behaves identically. Byte-for-byte diagnostics preserved;
  characterization suite green.
- Tests: `TestNullableTransport` in `test_pilot_run.py` (nulls
  pass on raw AND pre-converted paths; empty-string ≠ null
  distinguished). Fixture iterations also documented the
  v1.1 shape (integer id, string difficulty 1-10, 3-object
  examples, per-POS word_family, 10-key translations).
- Re-smoke (NEW run RUN-SMOKE-2, NEW dir `output/pilot_smoke2`;
  smoke-1 immutable): status ok, zero failures — structure,
  runtime, output_hash, schema, required_fields, example_count,
  target_word, mnemonic all pass (pos_alignment unverified,
  non-failing); guard clean; BT-05 history captured.
- Suite: 138 passed (incl. characterization). Pre-existing
  fixture failure unchanged.
- NOT done: the 1,000-entry execution. Awaiting explicit
  authorization with cost/time bounds.

## Execution record (smoke)

- New module `evaluation/pilot_run.py` (injectable generate fn;
  no DB; outputs to out_dir only): BT-04 input fold →
  v2.2.3 prompt fill (CEFR input = evidence label, recorded) →
  envelope → validator seam → BT-08 guard → BT-05 record →
  raw + report + history. Failures recorded as failed, never
  silent.
- New tests `evaluation/test_pilot_run.py`: 4 passed (stub
  success/invalid-JSON/refusal/provenance-line paths).
- Auth pre-check: `AUTH_OK` on gemini-3.8-flash. Repo online
  runner CANNOT run v2.2.3 (raises: thinking not implemented) —
  recorded; batch path or direct calls required.
- LIVE smoke, manifest entry 14 (this/det), exact v2.2.3 params
  (temp 1.0, thinking LOW, grounding off, stripped v1.1 schema):
  status partial. Structure pass, runtime pass, output_hash
  pass; SCHEMA_VIOLATION "None is not of type 'string'" at
  /phonetic_uk and /senses[0]/mnemonic_ar. Guard clean.
  BT-05 history captured (1 row, status partial, manifest hash
  pinned). Outputs: `output/pilot_smoke/`.
- BLOCKING FINDING for the full run: the model correctly emits
  the locked NULL semantics (phonetic_uk null = same-as-US per
  AGENTS.md; null mnemonic valid per §18), but the
  v1.1-candidate schema types those fields string-only. Scaling
  to 1,000 now would reproduce this failure ~1,000 times.
  Required: explicit nullable-schema ruling (relax schema vs
  force strings) BEFORE the full run. No stealth migration:
  smoke outputs sit under `.scratch` output only; zero
  canonical writes.
- Suite: 115 passed. Pre-existing fixture failure unchanged.

- [ ] Regen obeys exact-token + sense/POS + no-length-CEFR rules
- [ ] Every output carries complete versioning (BT-05
  instrumentation verified, no untraceable rows)
- [ ] Human eval blind, field-by-field, identity map separate
- [ ] Report states experiment evidence only; Gates A/B status
  restated, not assumed away
