"""Pilot execution runner (build ticket 12).

Implements spec section 7 (pilot) on the frozen manifest. One entry
at a time: fold input (BT-04) -> prompt (v2.2.3) -> generate
(injected fn; online Vertex or stub) -> envelope -> validate
(validator seam) -> BT-08 guard -> BT-05 provenance record ->
raw + report on disk. Failures are recorded as failed, never
silent. No DB access; outputs land under the given out_dir only
(never a migration: no canonical store is written anywhere).

CEFR input to the prompt uses the manifest's legacy evidence label,
recorded as generation input only — never a canonical assignment.
"""

import json
import os

from evaluation.artifact_validator import validate_artifact
from evaluation.deterministic_repairs import ci_guard_learner_text
from evaluation.identity import (
    build_key,
    is_single_word_candidate,
    normalize_lemma,
)
from evaluation.run_provenance import (
    append_history,
    build_generation_record,
)
from evaluation.utils import canonical_hash, utc_now

PROMPT_ID = "lexical_enrichment_final_m3"
PROMPT_VERSION = "2.2.3"
SCHEMA_ID = "lexical_output"
SCHEMA_VERSION = "v1.1-candidate"
MODEL_PROVIDER = "google"
MODEL_ID = "gemini-3.8-flash"
TEMPERATURE = 1.0
THINKING_MODE = "low"
GROUNDING_MODE = "off"
EXPERIMENT_ID = "PILOT-V1"


def build_prompt(prompt_template, entry):
    """Fill the v2.2.3 template. cefr input is the evidence label."""
    lemma = normalize_lemma(entry["lemma"])
    if not is_single_word_candidate(lemma):
        raise ValueError("manifest entry not a single-word form: %r" % (entry,))
    build_key(lemma, entry["pos"])  # POS must be canonical
    return prompt_template.format(
        lemma=entry["lemma"],
        pos=entry["pos"],
        cefr=entry["stratum"][0],
        id=entry["id"],
    )


def _iter_learner_texts(output):
    if not isinstance(output, dict):
        return
    senses = output.get("senses") or []
    if isinstance(senses, dict):
        senses = [senses]
    for sense in senses:
        if not isinstance(sense, dict):
            continue
        for field in ("definition_en", "definition_ar"):
            if sense.get(field):
                yield field, sense[field]
        for key in ("examples", "example_sentences"):
            examples = sense.get(key) or []
            if isinstance(examples, list):
                for i, ex in enumerate(examples):
                    text = ex if isinstance(ex, str) else (
                        ex.get("text") if isinstance(ex, dict) else None)
                    if text:
                        yield "%s[%d]" % (key, i), text
    for field in ("mnemonic_ar", "usage_note", "usageNote"):
        if output.get(field):
            yield field, output[field]


def run_one(entry, manifest_meta, prompt_template, schema, generate_fn,
            out_dir, run_id):
    """Execute one manifest entry end-to-end. Returns the report dict."""
    candidate_id = "%s-CAND-%s" % (EXPERIMENT_ID, entry["id"])
    report = {
        "candidate_id": candidate_id,
        "manifest_id": manifest_meta["manifest_id"],
        "status": "failed",
        "validator": None,
        "guard_defects": {},
        "provenance_line": None,
    }
    try:
        prompt_text = build_prompt(prompt_template, entry)
        raw_text = generate_fn(prompt_text)
        output = json.loads(raw_text)
        envelope = {
            "candidate_id": candidate_id,
            "experiment_id": EXPERIMENT_ID,
            "lexical_entry": {
                "lexical_id": candidate_id,
                "lemma": entry["lemma"],
                "pos": entry["pos"],
                "cefr": entry["stratum"][0],
            },
            "runtime": {"status": "success"},
            "output": output,
            "provenance": {
                "output_hash": canonical_hash(output),
                "golden_set_hash": None,
                "schema_version": SCHEMA_VERSION,
                "pilot_manifest_id": manifest_meta["manifest_id"],
                "pilot_manifest_hash": manifest_meta["manifest_hash"],
                "cefr_input_role": "evidence_label_only",
            },
        }
        checks, failures, flags = validate_artifact(
            envelope, EXPERIMENT_ID, schema)
        guard_defects = {}
        for field, text in _iter_learner_texts(output):
            defects = ci_guard_learner_text(text)
            if defects:
                guard_defects[field] = defects
        record = build_generation_record(
            output,
            prompt={"prompt_id": PROMPT_ID,
                    "prompt_version": PROMPT_VERSION},
            schema={"schema_id": SCHEMA_ID,
                    "schema_version": SCHEMA_VERSION},
            model={"provider": MODEL_PROVIDER, "model_id": MODEL_ID,
                   "model_version": MODEL_ID},
            generation_config={"temperature": TEMPERATURE},
            reasoning_grounding={"thinking_mode": THINKING_MODE,
                                 "grounding_mode": GROUNDING_MODE},
            run={"experiment_id": EXPERIMENT_ID, "run_id": run_id,
                 "input_snapshot_id": manifest_meta["manifest_id"],
                 "input_snapshot_hash": manifest_meta["manifest_hash"]},
            integrity={"output_hash": canonical_hash(output),
                       "status": "ok" if not failures else "partial"},
        )
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, candidate_id + ".json"),
                  "w", encoding="utf-8") as f:
            json.dump(envelope, f, ensure_ascii=False, indent=1)
        report["provenance_line"] = append_history(
            os.path.join(out_dir, "history.jsonl"), record)
        report["status"] = "ok" if not failures else "partial"
        report["validator"] = {"checks": checks, "failures": failures,
                               "flags": flags}
        report["guard_defects"] = guard_defects
        report["validated_at"] = utc_now()
    except Exception as exc:  # failure accounting, never silent
        report["status"] = "failed"
        report["error"] = "%s: %s" % (type(exc).__name__, exc)
    with open(os.path.join(out_dir, candidate_id + ".report.json"),
              "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return report
