# 05: LLM-versioning instrumentation (BT-12)

**What to build:** versioning instrumentation capturing all 7 locked
provenance dimensions on every LLM output (prompt id/version, schema
id/version, provider, model id/version, generation config incl.
temperature, thinking/grounding config, experiment/run IDs,
timestamp, input snapshot/hash, output hash, status) with
append-only history — in place before any pilot output exists.

**Blocked by:** None (can start immediately).

**Status:** resolved

**Spec ref:** spec §4 (LLM versioning); wayfinding 11 (DEFERRED,
anti-forgetting clause); v2.2.3 held as candidate only.

## Implementation record

- New module `evaluation/run_provenance.py` (no DB, no network):
  `build_generation_record` (refuses any missing dimension, bad
  status, or output-hash mismatch), `verify_record` (defect list;
  stale cache = defect, never truth), `append_history` /
  `read_history` (JSONL, creates parents, returns line numbers).
  Append-only by construction: no update/delete/overwrite/replace/
  upsert API exists (asserted by test).
- All 7 dimension groups enforced via `REQUIRED_DIMENSIONS`
  (prompt, schema, model+provider, generation config incl.
  temperature + material extras, thinking/grounding, run incl.
  input snapshot id+hash, integrity incl. output hash + status);
  `generated_at` defaults to now; parenthetical list treated as
  minimum contents, not blobs.
- New tests `evaluation/test_run_provenance.py`: 10 passed
  (per-group and per-field omission refusal, hash/status
  enforcement, stale-cache detection, append order, defective
  append refused without creating the file).
- Fixed during execution: test-only bug (`del` of a defaulted
  field); module correct throughout.
- Suite state: new + identity + validator + utils = 55 passed.
  Pre-existing baseline defect UNCHANGED and still flagged:
  `test_input_builder_determinism` fails on the missing
  `gemini_flash_v1.1_batch_pilot.json` fixture. NOT repaired
  here per order (instrumentation does not touch that path).
- Scope held: instrumentation only. No runner rewiring, no
  configuration choice, no v2.2.3 promotion. BT-11 wiring is
  downstream work, not this ticket.

- [ ] All 7 dimension groups recorded per output, none omittable
- [ ] Regen creates a new history record; no silent replace path
- [ ] Input snapshot/hash captured (not just model identity)
- [ ] BT-11 cannot produce untraceable output after this lands
