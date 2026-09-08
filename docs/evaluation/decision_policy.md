# Decision Policy
**Version**: v1.1 (FROZEN FOR CALIBRATION) | **Date**: 2026-09-01

## Purpose

This policy defines the rules used by the Decision Engine (`phase_eval_decision.py`) to assign a final verdict to each word after Machine + LLM evaluation completes. It encodes the **Hybrid Enrichment Strategy**, where Legacy is treated as the pedagogical baseline, and V2 is used as an enrichment layer.

---

## Decision Categories

### 🟢 KEEP_LEGACY

**Condition**: Legacy data is pedagogically superior or equivalent, and V2 provides no distinct missing fields to merge.

**Apply when**:
- Machine validation: `pass`
- LLM Judge winner: `legacy` or `tie`
- No critical Legacy gaps that V2 successfully filled (e.g., both are missing UK IPA, or both have it).

**Action**: No V2 generation needed. Legacy data migrates as-is.

---

### 🟡 ENRICH (Field-level Merge)

**Condition**: Either V2 is better overall but loses critical Legacy data, OR Legacy is better overall but V2 fills specific gaps (e.g., Phonetics).

**Apply when**:
- Machine validation: `pass`
- LLM Judge winner: `v2`, but `loss_score > 0.0` (V2 lost the legacy mnemonic or Arabic definition).
- OR LLM Judge winner: `legacy`, but V2 added distinct new fields (e.g., `phonetic_uk: added`).

**Action**: Do not regenerate the whole word. Retain Legacy's `mnemonicAr`, `definitionAr`, and `usageNote` (the pedagogical gold). Selectively inject only the specific fields V2 improved (e.g., `phonetic_uk`, `senses` if they don't overwrite the core definition).

---

### 🔵 REGENERATE (Full Replacement)

**Condition**: V2 is meaningfully and clearly better than Legacy across multiple dimensions, AND there is absolutely no loss of legacy knowledge.

**Apply when**:
- Machine validation: `pass`
- LLM Judge winner: `v2` with `improvement: major`
- Preservation Score: 1.0 (No loss of legacy fields; `loss_score == 0.0`).

**Action**: Replace Legacy content entirely with V2 generated content.

---

### 🔴 MANUAL_REVIEW

**Condition**: Conflicting signals, ambiguous data, or machine validation failure.

**Apply when**:
- Machine validation ≠ `pass`
- LLM Judge: `winner = insufficient_evidence`
- LLM Judge decision fundamentally conflicts with Guardrails (e.g., recommending REGENERATE when `loss_score > 0`).

**Action**: Flag for human decision. Do not auto-apply any changes.

---

## Decision Matrix

| LLM Winner | Legacy Loss (`loss_score`) | V2 Additions | Decision |
|:---|:---|:---|:---|
| legacy / tie | 0.0 | None | KEEP_LEGACY |
| legacy / tie | 0.0 | Yes (e.g., UK IPA) | ENRICH |
| v2 | 0.0 | Any | REGENERATE |
| v2 | > 0.0 | Any | ENRICH (Block Replace, Merge only) |
| insufficient | Any | Any | MANUAL_REVIEW |

---

## Important Constraints

1. **Legacy is the Pedagogical Source:** Do not lightly overwrite Legacy `mnemonicAr` or `definitionAr` unless V2 explicitly scores higher in `ARA` and `MNE`.
2. **loss_score > 0 is a Guardrail:** If `loss_score = 1.0`, full REGENERATE is blocked regardless of how high V2 scores overall. It forces an ENRICH path.
3. **Field-level Regeneration:** In production, if only a specific field is missing (e.g. UK IPA), only that field should be prompted for generation to save costs.

---

## Known Open Questions (to resolve after Phase C)

- [ ] What is the minimum `improvement_score` delta that justifies REGENERATE vs ENRICH?
- [ ] Should V2's UK IPA defect (5 words) be fixed via prompt change or via IELTS dataset sourcing?
- [ ] What is the estimated cost-per-word for Phases 2–4 generation, and how does it affect the ROI threshold?
- [ ] For the 86 words where V2 added UK IPA: how often does the V2-generated UK IPA match the IELTS dataset? (cross-reference quality check)
