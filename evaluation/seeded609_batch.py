"""Vertex Batch transport for the Ticket-19 609 remediation experiment.

New experiment (EXP-SEEDED-609), frozen methodology: reuses the proven
two-phase machinery's pure functions from evaluation.seeded_batch
(request building, import, validator gate) with NEW run dirs and a NEW
GCS prefix. Phase A (generation) ONLY — no decision phase: the Ticket 18
triage manifest is the scope record and the blind judge compares candidate
vs legacy directly (authorized Ticket-19 pipeline).

Frozen (imported, never redefined): build_generation_requests, key_of,
storage_key_of, import_generation_records, load_config, load_prompt,
_client, _upload, _file_hash, _job_succeeded, _job_failed,
_download_output_lines. Model/prompt/temp come from the frozen config
evaluation/configs/seeded_001A_pilot60_config.json (gemini-3.8-flash,
seeded v1.1, temperature 0).

Usage:
  GOOGLE_APPLICATION_CREDENTIALS=<key> python -m evaluation.seeded609_batch submit-a
  GOOGLE_APPLICATION_CREDENTIALS=<key> python -m evaluation.seeded609_batch poll-a --wait-minutes 60
  GOOGLE_APPLICATION_CREDENTIALS=<key> python -m evaluation.seeded609_batch status
"""

import argparse
import json
import os
import sys
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.seeded_batch import (
    _client,
    _download_output_lines,
    _file_hash,
    _job_failed,
    _job_succeeded,
    _upload,
    build_generation_requests,
    import_generation_records,
    key_of,
    load_config,
    load_prompt,
    storage_key_of,
)
from evaluation.utils import utc_now
from google.genai.types import CreateBatchJobConfig

BUCKET = "lexical-enrichment"
GCS_RUN_PREFIX = "seeded609/exp-seeded-609"
RUN_DIR = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                       "output", "EXP-SEEDED-609", "generated_609")
BATCH_SUBDIR = os.path.join(RUN_DIR, "batch")
SNAPSHOT = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                        "output", "EXP-SEEDED-609", "seed_snapshot_609.jsonl")


def load_seeds_609():
    with open(SNAPSHOT, encoding="utf-8") as f:
        seeds = [json.loads(line) for line in f if line.strip()]
    index = {"%s/%s" % (s["lemma"].strip().lower(),
                        (s.get("pos") or "").strip().lower()): s
             for s in seeds}
    identities = [{"lemma": s["lemma"], "pos": s["pos"],
                   "cefr": s["seed"].get("cefr")} for s in seeds]
    return seeds, index, identities


def _escape_percent(obj):
    """Transport encoding for the frozen %-formatter (seeded_generator.
    build_generation_prompt interpolates the seed JSON with %): every
    literal % becomes %%, which the formatter renders back to % exactly.
    Zero content effect; the model sees the true seed bytes. 356 seeds
    needed no escaping (no % present); 4 of the 609 do."""
    if isinstance(obj, str):
        return obj.replace("%", "%%")
    if isinstance(obj, dict):
        return {k: _escape_percent(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_escape_percent(v) for v in obj]
    return obj


def escaped_index(index):
    """Deep copy of the seed index with %-escaping applied to seed blobs."""
    out = {}
    for key, rec in index.items():
        rec2 = dict(rec)
        rec2["seed"] = _escape_percent(rec["seed"])
        out[key] = rec2
    return out


def escaped_keys(index):
    """Identity keys whose seed text contains a literal % (accounting)."""
    found = []
    for key, rec in index.items():
        if "%" in json.dumps(rec["seed"], ensure_ascii=False):
            found.append(key)
    return sorted(found)


def load_progress():
    path = os.path.join(RUN_DIR, "progress.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"items": {}}


def save_progress(progress):
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "progress.json"), "w",
              encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=1)


def load_state():
    path = os.path.join(BATCH_SUBDIR, "state_a.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(state):
    os.makedirs(BATCH_SUBDIR, exist_ok=True)
    with open(os.path.join(BATCH_SUBDIR, "state_a.json"), "w",
              encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def append_provenance(entry):
    path = os.path.join(RUN_DIR, "seeded_generation_provenance.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def cmd_submit_a():
    _seeds, index, identities = load_seeds_609()
    cfg = load_config()
    progress = load_progress()
    done = {k for k, v in progress.get("items", {}).items()
            if v.get("status") == "success"}
    remaining = [i for i in identities if key_of(i) not in done]
    state = load_state()
    if state:
        print("state_a exists (status=%s); refusing double submit"
              % state.get("status"))
        return
    prompt_text, prompt_hash = load_prompt()
    esc_keys = escaped_keys(index)
    index = escaped_index(index)
    reqs = build_generation_requests(remaining, index, prompt_text)
    os.makedirs(BATCH_SUBDIR, exist_ok=True)
    req_path = os.path.join(BATCH_SUBDIR, "requests_a.jsonl")
    with open(req_path, "w", encoding="utf-8") as f:
        for req in reqs:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")
    in_hash = _file_hash(req_path)
    blob_name = "%s/input_a/requests.jsonl" % GCS_RUN_PREFIX
    uri = _upload(req_path, blob_name)
    out_prefix = "gs://%s/%s/output_a" % (BUCKET, GCS_RUN_PREFIX)
    client = _client(cfg)
    job = client.batches.create(
        model=cfg["model_id"], src=uri,
        config=CreateBatchJobConfig(dest=out_prefix))
    job_id = getattr(job, "name", str(job))
    submitted = [{"key": key_of(i), "lemma": i["lemma"],
                  "pos": i.get("pos"), "cefr": i.get("cefr")}
                 for i in remaining]
    save_state({
        "status": "running", "job_id": job_id, "input_gcs": uri,
        "output_gcs": out_prefix, "submitted": submitted,
        "input_hash": in_hash, "prompt_hash": prompt_hash,
        "model": cfg["model_id"], "created_at": utc_now(),
        "percent_escaped_keys": esc_keys})
    print("Batch 609-A submitted: %d requests, job %s" % (len(reqs), job_id))


def cmd_poll_a(wait_minutes=0):
    cfg = load_config()
    state = load_state()
    if not state:
        print("no state_a; run submit-a first")
        return
    if state.get("status") == "imported":
        print("state_a already imported (%d submitted)"
              % len(state["submitted"]))
        return
    client = _client(cfg)
    job = client.batches.get(name=state["job_id"])
    print("job state: %s" % getattr(job, "state", "?"))
    deadline = time.monotonic() + float(wait_minutes or 0) * 60
    while not (_job_succeeded(job) or _job_failed(job)):
        if wait_minutes and time.monotonic() > deadline:
            print("still running; poll again later")
            return
        time.sleep(30)
        job = client.batches.get(name=state["job_id"])
        print("job state: %s" % getattr(job, "state", "?"))
    if _job_failed(job):
        state["status"] = "failed"
        state["error"] = str(getattr(job, "error", ""))
        save_state(state)
        print("BATCH 609-A FAILED: %s" % state["error"])
        return
    _seeds, index, _identities = load_seeds_609()
    submitted_map = {s["key"].replace("/", "__"): s for s in
                     state["submitted"]}
    lines = _download_output_lines(state["output_gcs"],
                                   os.path.join(BATCH_SUBDIR, "outputs_a"))
    outcomes = import_generation_records(
        lines, submitted_map, index, state["prompt_hash"], state["model"],
        {"job_id": state["job_id"], "input_gcs": state["input_gcs"],
         "output_gcs": state["output_gcs"]})
    progress = load_progress()
    imported = passed = failed = 0
    os.makedirs(os.path.join(RUN_DIR, "raw"), exist_ok=True)
    for key, entry, err, artifact_pass, candidate, arm in outcomes:
        if key is None or entry is None:
            failed += 1
            if key is not None:
                progress.setdefault("items", {})[key] = {
                    "status": "error", "message": err}
            continue
        with open(os.path.join(RUN_DIR, "raw",
                               key.replace("/", "__") + ".json"),
                  "w", encoding="utf-8") as f:
            json.dump({"identity": entry["identity"],
                       "candidate": candidate,
                       "arm": arm},
                      f, ensure_ascii=False, indent=1)
        append_provenance(entry)
        imported += 1
        if artifact_pass:
            passed += 1
        else:
            failed += 1
        progress.setdefault("items", {})[key] = {
            "status": "success", "artifact_pass": artifact_pass}
    save_progress(progress)
    state["status"] = "imported"
    state["imported_at"] = utc_now()
    save_state(state)
    print("Batch 609-A imported: %d lines, %d mapped, %d pass, %d fail/err"
          % (len(lines), imported, passed, failed))


def cmd_status():
    state = load_state()
    if state:
        print("state_a: status=%s job=%s submitted=%d"
              % (state.get("status"), state.get("job_id"),
                 len(state.get("submitted", []))))
    else:
        print("state_a: none")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["submit-a", "poll-a", "status"])
    parser.add_argument("--wait-minutes", type=int, default=0)
    args = parser.parse_args()
    if args.cmd == "submit-a":
        cmd_submit_a()
    elif args.cmd == "poll-a":
        cmd_poll_a(args.wait_minutes)
    elif args.cmd == "status":
        cmd_status()


if __name__ == "__main__":
    main()
