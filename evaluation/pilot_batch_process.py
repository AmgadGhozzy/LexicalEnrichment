"""Batch output processing (build ticket 12, 356-row completion).

Reads Vertex batch prediction rows (already generated, immutable
input) and runs each MODEL_TEXT row through: envelope ->
validator seam -> BT-08 guard -> BT-05 provenance record ->
per-entry report. Empty-payload rows are classified WITHOUT
linguistic attribution (infrastructure failure, never model or
validator failure). No DB access; no canonical writes; raw batch
output never modified. No retries live here (retry policy belongs
to the run decision, with its own provenance when authorized).
"""

import json

from evaluation.artifact_validator import validate_artifact
from evaluation.deterministic_repairs import ci_guard_learner_text
from evaluation.pilot_run import (
    EXPERIMENT_ID,
    MODEL_ID,
    MODEL_PROVIDER,
    PROMPT_ID,
    PROMPT_VERSION,
    SCHEMA_ID,
    SCHEMA_VERSION,
    TEMPERATURE,
    THINKING_MODE,
    GROUNDING_MODE,
    _iter_learner_texts,  # shared guard-iteration; single owner: pilot_run
)
from evaluation.run_provenance import (
    append_history,
    build_generation_record,
)
from evaluation.utils import canonical_hash, utc_now

BATCH_RUN_ID = "RUN-BATCH-1"


def extract_model_text(batch_row):
    """Return (ok, text_or_class).

    ok=True with the model text when the row carries a candidate
    payload; ok=False with 'empty_payload' when the response holds
    no evaluable content (infrastructure failure class — never a
    linguistic verdict).
    """
    try:
        text = batch_row["response"]["candidates"][0]["content"][
            "parts"][0]["text"]
        if not isinstance(text, str) or not text.strip():
            return (False, "empty_payload")
        return (True, text)
    except (KeyError, TypeError, IndexError):
        return (False, "empty_payload")


def process_row(batch_row, manifest_entry, manifest_meta, schema,
                history_path, reports_dir, run_id=BATCH_RUN_ID,
                job_id=None):
    """Process one batch row. Returns the report dict (always)."""
    import os

    key = batch_row.get("key", "UNKNOWN-KEY")
    report = {
        "key": key,
        "manifest_id": manifest_meta["manifest_id"],
        "run_id": run_id,
        "status": "failed",
        "failure_class": None,
    }
    ok, payload = extract_model_text(batch_row)
    if not ok:
        report["failure_class"] = "infrastructure_empty_payload"
        report["note"] = ("no evaluable model payload; no linguistic, "
                          "validator, or model attribution possible")
        return report
    try:
        output = json.loads(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        report["failure_class"] = "unparseable_output"
        report["error"] = "%s: %s" % (type(exc).__name__, exc)
        return report
    envelope = {
        "candidate_id": key,
        "experiment_id": EXPERIMENT_ID,
        "lexical_entry": {
            "lexical_id": key,
            "lemma": manifest_entry["lemma"],
            "pos": manifest_entry["pos"],
            "cefr": manifest_entry["stratum"][0],
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
            "batch_job_id": job_id,
        },
    }
    checks, failures, flags = validate_artifact(
        envelope, EXPERIMENT_ID, schema)
    guard_defects = {}
    for field, text in _iter_learner_texts(output):
        defects = ci_guard_learner_text(text)
        if defects:
            guard_defects[field] = defects
    run_group = {
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "input_snapshot_id": manifest_meta["manifest_id"],
        "input_snapshot_hash": manifest_meta["manifest_hash"],
    }
    if job_id:
        run_group["batch_job_id"] = job_id
    record = build_generation_record(
        output,
        prompt={"prompt_id": PROMPT_ID, "prompt_version": PROMPT_VERSION},
        schema={"schema_id": SCHEMA_ID, "schema_version": SCHEMA_VERSION},
        model={"provider": MODEL_PROVIDER, "model_id": MODEL_ID,
               "model_version": MODEL_ID},
        generation_config={"temperature": TEMPERATURE},
        reasoning_grounding={"thinking_mode": THINKING_MODE,
                             "grounding_mode": GROUNDING_MODE},
        run=run_group,
        integrity={"output_hash": canonical_hash(output),
                   "status": "ok" if not failures else "partial"},
    )
    os.makedirs(reports_dir, exist_ok=True)
    with open(os.path.join(reports_dir, key + ".json"),
              "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=1)
    report["provenance_line"] = append_history(history_path, record)
    report["status"] = "ok" if not failures else "partial"
    report["failure_class"] = None if not failures else "validator_findings"
    report["validator"] = {"checks": checks, "failures": failures,
                           "flags": flags}
    report["guard_defects"] = guard_defects
    report["validated_at"] = utc_now()
    return report
