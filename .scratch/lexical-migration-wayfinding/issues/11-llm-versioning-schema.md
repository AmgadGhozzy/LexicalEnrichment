Type: grilling
Status: resolved

## Question

What is the exact schema for LLM enrichment versioning / output history (prompt version, schema version, model, temperature, thinking/grounding, run linkage)?

## Evidence

- Current approved experimental candidate v2.2.3 (prompt `lexical_enrichment_final_m3.txt`, schema v1.1-candidate, gemini-3.8-flash, temp 1.0, thinking low, grounding off; HR-104: 0 critical errors) — candidate for experiments, not production truth.
- `AGENTS.md`: transport strips `$schema`/`schema_version` on send; semantic NULL preserved; no 500+ scale-up without fixing batch resume/retry/cost-log.

## Gate

DEFERRED — resolved as deferred. Physical DDL to `/to-spec`/pilot; semantic dimensions locked now. Do not invent the schema now; the deferral is explicit and bound.

## Answer

Defer the physical LLM-versioning DDL to /to-spec and pilot implementation, but lock the minimum provenance/versioning dimensions now.

Every LLM enrichment output MUST be traceable to the exact generation configuration and input state that produced it.

Minimum required dimensions:

1. Prompt
   - prompt identifier
   - prompt version

2. Output schema
   - schema identifier
   - schema version

3. Model
   - provider
   - model identifier/version

4. Generation configuration
   - temperature
   - other materially relevant generation parameters when used, including values such as top-p, top-k, and maximum output tokens where applicable

5. Reasoning/grounding configuration
   - thinking/reasoning mode or configuration
   - grounding mode/configuration
   - any selected grounding/search mode where applicable

6. Experiment/run provenance
   - experiment identifier
   - run/batch identifier
   - generation timestamp
   - input dataset/snapshot identifier or hash

7. Integrity
   - output hash
   - generation status

The versioning contract is append-only: a regenerated output creates a new version/history record rather than silently replacing the previous output.

Physical table/column layout, foreign keys, indexes, and storage mechanics are deferred to /to-spec and pilot implementation.

Anti-forgetting requirement:
- /to-spec MUST contain an explicit LLM-versioning section resolving Ticket 11 before any pilot is considered shippable.
- DEFERRED means scheduled for specification/implementation, not abandoned.
- No implementation may omit a locked provenance dimension merely because the physical schema has not yet been selected.

Experimental status:
- v2.2.3 remains the approved experimental candidate based on HR-104.
- It is NOT production truth.
- No broad model/temperature sweep is authorized before the data architecture and deterministic preprocessing decisions are settled.

Gate: RESOLVED / DEFERRED
