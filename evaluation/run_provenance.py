"""LLM-versioning instrumentation (build ticket 05, spec section 4).

Every LLM enrichment output must be traceable across the 7 locked
provenance dimensions (wayfinding 11). This module builds, verifies,
and appends generation records. It is append-only by construction:
there is deliberately NO update/delete API — a regen creates a new
record. Pure functions + one append; no DB access.

The 7 locked dimension groups:
  1. prompt id/version            5. thinking/grounding config
  2. schema id/version            6. experiment/run provenance
  3. provider + model id/version     (experiment id, run/batch id,
  4. generation config               timestamp, input snapshot/hash)
     (temperature + material       7. integrity (output hash, status)
     params where used)
"""

import json
import os

from evaluation.utils import canonical_hash, utc_now

# group -> required fields. None omittable (ticket acceptance).
REQUIRED_DIMENSIONS = {
    "prompt": ("prompt_id", "prompt_version"),
    "schema": ("schema_id", "schema_version"),
    "model": ("provider", "model_id", "model_version"),
    "generation_config": ("temperature",),
    "reasoning_grounding": ("thinking_mode", "grounding_mode"),
    "run": (
        "experiment_id",
        "run_id",
        "generated_at",
        "input_snapshot_id",
        "input_snapshot_hash",
    ),
    "integrity": ("output_hash", "status"),
}

VALID_STATUSES = frozenset({"ok", "failed", "partial"})


def _require(mapping, group, fields):
    missing = [f for f in fields if not mapping.get(f)]
    if missing:
        raise ValueError(
            "generation record missing %s dimensions: %s"
            % (group, ", ".join(missing))
        )


def build_generation_record(output, **dimensions):
    """Build a complete versioning record for one LLM output.

    `output` is the generated payload (hashed, never embedded).
    `dimensions` must supply every REQUIRED_DIMENSIONS field;
    `generated_at` defaults to now; extra material generation
    params (top_p, top_k, max_output_tokens, ...) ride inside
    `generation_config` as a nested dict under key "extra".
    Raises ValueError on any missing dimension or bad status.
    """
    dims = dict(dimensions)
    run = dict(dims.get("run", {}))
    run.setdefault("generated_at", utc_now())
    dims["run"] = run
    for group, fields in REQUIRED_DIMENSIONS.items():
        _require(dims.get(group, {}), group, fields)
    if dims["integrity"]["status"] not in VALID_STATUSES:
        raise ValueError(
            "status %r not in %s"
            % (dims["integrity"]["status"], sorted(VALID_STATUSES))
        )
    expected = canonical_hash(output)
    if dims["integrity"]["output_hash"] != expected:
        raise ValueError("output_hash does not match canonical_hash(output)")
    record = {"version": 1}
    for group in REQUIRED_DIMENSIONS:
        record[group] = dims[group]
    return record


def verify_record(record, output=None):
    """Check a record's completeness (and output hash when given).

    Returns a list of defect strings; empty means valid. A record
    missing any locked dimension, carrying a bad status, or whose
    output_hash mismatches the supplied output is defective —
    never a second source of truth, just a broken cache entry.
    """
    defects = []
    if not isinstance(record, dict):
        return ["record is not a mapping"]
    for group, fields in REQUIRED_DIMENSIONS.items():
        section = record.get(group)
        if not isinstance(section, dict):
            defects.append("missing group: %s" % group)
            continue
        for field in fields:
            if not section.get(field):
                defects.append("missing %s.%s" % (group, field))
    status = (record.get("integrity") or {}).get("status")
    if status not in VALID_STATUSES:
        defects.append("bad status: %r" % (status,))
    if output is not None:
        if canonical_hash(output) != (record.get("integrity") or {}).get(
            "output_hash"
        ):
            defects.append("output_hash mismatch")
    return defects


def append_history(history_path, record):
    """Append one record (JSON line) to a history file. Never overwrites.

    Creates parent directories as needed. Returns the 1-based line
    number of the appended record.
    """
    defects = verify_record(record)
    if defects:
        raise ValueError("refusing to append defective record: %s" % defects)
    directory = os.path.dirname(os.path.abspath(history_path))
    os.makedirs(directory, exist_ok=True)
    line_no = 0
    if os.path.exists(history_path):
        with open(history_path, encoding="utf-8") as f:
            line_no = sum(1 for _ in f)
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return line_no + 1


def read_history(history_path):
    """Read all records back, in append order."""
    with open(history_path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
