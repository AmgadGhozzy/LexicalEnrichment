# Architectural Decision Records (ADR)

## ADR-001: Selection of Prompt v1.1.0 for Batch Pilot

**Date:** 2026-09-02
**Status:** Accepted Candidate

### Context
We have completed Step 8A.11 (Prompt Evaluation). The goal was to identify the exact-target compliance rate of our prompts for generating lexical enrichment artifacts before moving to the Batch Pilot (Step 8A.12). 

### Evidence & Metrics

**Baseline:**
* Experiment: `EXP-2026-09-02-010`
* Prompt: `v1.0.0`
* Golden Set: 160 entries (1 missing artifact in run)
* Validated artifacts: 159
* `TARGET_WORD_MISSING`: 30
* Exact-target compliance: 81.13%
* Compliance failure rate: 18.87%

**Refined Candidate:**
* Experiment: `EXP-2026-09-02-012`
* Prompt: `v1.1.0`
* Golden Set: `golden_v2.json`
* Validated artifacts: 160
* `TARGET_WORD_MISSING`: 3
* Exact-target compliance: 98.13%
* Compliance failure rate: 1.87%
* Schema/structure failures: 0
* Hash/integrity failures: 0
* Runner failures: 0

### Decision
`selected_prompt_version = 1.1.0`

We will proceed with Prompt v1.1.0 as the selected prompt candidate pending Batch Pilot and human evaluation. This is not yet a final production prompt.

### Acceptance Notes
The 3 remaining failures in v1.1.0 were:
- `decision-making`
- `long-standing`
- `interval`

These are exact-target compliance failures (the model generated a morphologically different but semantically valid variant, e.g. "decision making" instead of "decision-making"). They are not general semantic-quality failures. 

The deterministic validator remains unchanged and its logic for exact-target matching is maintained. Experiments `EXP-2026-09-02-010` and `EXP-2026-09-02-012` are considered immutable evidence of this baseline comparison.
