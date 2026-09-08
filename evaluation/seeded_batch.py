"""Two-phase Vertex Batch transport for the EXP-SEEDED-001A full-356 run.

Phase A (generation): bulk seeded-generation requests for every identity
that is not already complete in the run dir. The 31 online successes are
frozen, never re-picked, never overwritten.

Phase B (decision audit): bulk decision-audit requests built ONLY from the
verified generation outputs (artifact/schema/hash/identity gate between the
two phases). Same DECISION_PROMPT contract, same model/temperature, same
seed-preservation classification as the online path.

Transport seam: every provenance write is tagged with channel=online|batch
so the run contract stays homogeneous; the evaluation DTO never carries
transport. Job submission and polling are resumable via state files.
"""

import argparse
import hashlib
import json
import os
import sys
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from google import genai
from google.cloud import storage
from google.genai.types import CreateBatchJobConfig

from evaluation.seeded_generator import (
    build_generation_prompt, load_seed_snapshot, parse_candidate,
    renormalize_candidate, validate_seeded_candidate, DECISION_PROMPT,
    source_type_for)
from evaluation.seed_preservation import FIELDS, seed_preservation_report
from evaluation.utils import utc_now

BUCKET = "lexical-enrichment"
GCS_RUN_PREFIX = "seeded356/exp-seeded-001a-356"
CONFIG = "evaluation/configs/seeded_001A_pilot60_config.json"
RUN_DIR = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build",
                       "output", "EXP-SEEDED-001A", "generated_356")
BATCH_SUBDIR = os.path.join(RUN_DIR, "batch")


def load_config():
    with open(os.path.join(ROOT_DIR, CONFIG), encoding="utf-8") as f:
        return json.load(f)


def load_seeds():
    cfg = load_config()
    seeds = load_seed_snapshot(os.path.join(ROOT_DIR, cfg["seed_snapshot"]))
    index = {"%s/%s" % (s["lemma"].strip().lower(),
                        (s.get("pos") or "").strip().lower()): s
             for s in seeds}
    identities = [{"lemma": s["lemma"], "pos": s["pos"],
                   "cefr": s["seed"].get("cefr")} for s in seeds]
    if len(seeds) != 356:
        raise RuntimeError("seed snapshot expected 356, got %d" % len(seeds))
    return seeds, index, identities, cfg


def key_of(identity):
    return "%s/%s" % (str(identity["lemma"]).strip().lower(),
                      (str(identity.get("pos")) or "").strip().lower())


def storage_key_of(identity):
    return key_of(identity).replace("/", "__")


def load_progress():
    path = os.path.join(RUN_DIR, "progress.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"items": {}}


def save_progress(progress):
    with open(os.path.join(RUN_DIR, "progress.json"), "w",
              encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=1)


def done_success_keys(progress):
    return {k for k, v in progress.get("items", {}).items()
            if v.get("status") == "success"}


def compute_remaining(identities, progress):
    done = done_success_keys(progress)
    return [i for i in identities if key_of(i) not in done]


def load_prompt():
    cfg = load_config()
    prompt_path = os.path.join(ROOT_DIR, cfg["prompt_path"])
    with open(prompt_path, encoding="utf-8") as f:
        prompt_text = f.read()
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    return prompt_text, prompt_hash


def load_state(phase):
    path = os.path.join(BATCH_SUBDIR, "state_%s.json" % phase)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(phase, state):
    os.makedirs(BATCH_SUBDIR, exist_ok=True)
    with open(os.path.join(BATCH_SUBDIR, "state_%s.json" % phase),
              "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def build_generation_requests(identities, index, prompt_text):
    lines = []
    for identity in identities:
        key = key_of(identity)
        seed_blob = index[key]["seed"]
        prompt = build_generation_prompt(identity, seed_blob, prompt_text)
        lines.append({
            "key": storage_key_of(identity),
            "request": {
                "contents": [{"role": "user",
                              "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0}}})
    return lines


def build_decision_requests(keys, index, load_raw):
    lines = []
    for key in keys:
        seed_blob = index[key]["seed"]
        artifact = load_raw(key)
        cursor, _arm = renormalize_candidate(artifact["candidate"])
        compact_legacy = {f: seed_blob.get(f) for f in FIELDS}
        compact_cand = {f: cursor.get(f) for f in FIELDS}
        prompt = DECISION_PROMPT.format(
            fields=", ".join(FIELDS),
            legacy=json.dumps(compact_legacy, ensure_ascii=False, indent=1),
            candidate=json.dumps(compact_cand, ensure_ascii=False, indent=1))
        key_b32 = key.replace("/", "__")
        lines.append({
            "key": key_b32,
            "request": {
                "contents": [{"role": "user",
                              "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0,
                                     "responseMimeType": "application/json"}}})
    return lines


def _client(cfg):
    return genai.Client(vertexai=True, project=cfg["project_id"],
                        location=cfg["location"])


def _upload(req_path, blob_name):
    sc = storage.Client()
    bucket = sc.bucket(BUCKET)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(req_path)
    return "gs://%s/%s" % (BUCKET, blob_name)


def _file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _job_succeeded(job):
    s = str(getattr(job, "state", "")).upper()
    return s.endswith("SUCCEEDED")


def _job_failed(job):
    s = str(getattr(job, "state", "")).upper()
    return s.endswith("FAILED") or s.endswith("CANCELLED")


def _download_output_lines(output_gcs, local_dir):
    prefix = output_gcs.replace("gs://", "").split("/", 1)[1]
    os.makedirs(local_dir, exist_ok=True)
    sc = storage.Client()
    bucket = sc.bucket(BUCKET)
    lines = []
    for blob in sorted(bucket.list_blobs(prefix=prefix)):
        if not blob.name.endswith(".jsonl"):
            continue
        local = os.path.join(local_dir, os.path.basename(blob.name))
        blob.download_to_filename(local)
        with open(local, encoding="utf-8") as f:
            lines.extend(f.readlines())
    return lines


def import_generation_records(lines, submitted_map, index, prompt_hash,
                              model, job_meta):
    outcomes = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            outcomes.append((None, None, "malformed_line: %s" % exc, False))
            continue
        key = rec.get("key")
        if not key:
            outcomes.append((None, None, "missing_key", False))
            continue
        identity = submitted_map.get(key)
        if identity is None:
            outcomes.append((key, None, "unknown_key", False))
            continue
        entry = None
        err = None
        candidate = None
        arm = None
        artifact_pass = False
        if "error" in rec:
            err = "batch_api_error: %s" % rec["error"]
        else:
            try:
                candidates = rec.get("response", {}).get("candidates", [])
                parts = candidates[0].get("content", {}).get("parts", [])
                raw_text = parts[0].get("text", "") if parts else ""
                candidate = parse_candidate(raw_text)
                cursor, arm = renormalize_candidate(candidate)
                checks, artifact_pass = validate_seeded_candidate(
                    candidate, identity, cursor)
                candidate_hash = hashlib.sha256(
                    json.dumps(candidate, sort_keys=True,
                               ensure_ascii=False).encode("utf-8")).hexdigest()
                entry = {
                    "identity": {"lemma": identity["lemma"],
                                 "pos": identity.get("pos"),
                                 "cefr": identity.get("cefr")},
                    "phase": "generation",
                    "channel": "batch",
                    "prompt_hash": prompt_hash,
                    "model": model,
                    "job_id": job_meta["job_id"],
                    "input_gcs": job_meta["input_gcs"],
                    "output_gcs": job_meta["output_gcs"],
                    "artifact_pass": artifact_pass,
                    "validator": checks,
                    "candidate_hash": candidate_hash,
                    "imported_at": utc_now(),
                }
            except Exception as exc:  # noqa: BLE001
                err = "parse_failed: %s" % exc
        outcomes.append((key, entry, err, artifact_pass,
                         candidate, arm))
    return outcomes


def import_decision_records(lines, submitted_map, index, model, job_meta):
    outcomes = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            outcomes.append((None, None, "malformed_line: %s" % exc))
            continue
        key = rec.get("key")
        if not key:
            outcomes.append((None, None, "missing_key"))
            continue
        identity = submitted_map.get(key)
        if identity is None:
            outcomes.append((key, None, "unknown_key"))
            continue
        seed_blob = index[identity["key"]]["seed"]
        artifact = _load_raw(identity["key"])
        cursor, _arm = renormalize_candidate(artifact["candidate"])
        err = None
        decisions_out = None
        if "error" in rec:
            err = "batch_api_error: %s" % rec["error"]
        else:
            try:
                candidates = rec.get("response", {}).get("candidates", [])
                parts = candidates[0].get("content", {}).get("parts", [])
                raw_text = parts[0].get("text", "") if parts else ""
                decisions_out = json.loads(raw_text.strip())
            except Exception as exc:  # noqa: BLE001
                err = "decisions_parse_failed: %s" % exc
        pres = seed_preservation_report(
            seed_blob, cursor, identity["lemma"],
            field_decisions=decisions_out)
        source_type = {}
        for f in FIELDS:
            source_type[f] = source_type_for(
                pres["fields"][f]["category"],
                (decisions_out or {}).get(f, {}).get("action"))
        entry = {
            "identity": {"lemma": identity["lemma"],
                         "pos": identity.get("pos"),
                         "cefr": identity.get("cefr")},
            "phase": "decision",
            "channel": "batch",
            "model": model,
            "job_id": job_meta["job_id"],
            "decisions_status": "ok" if decisions_out else (
                "error: %s" % err if err else "missing"),
            "field_decisions": decisions_out,
            "preservation": pres,
            "source_type": source_type,
            "imported_at": utc_now(),
        }
        outcomes.append((key, entry, err))
    return outcomes


def _load_raw(key):
    path = os.path.join(RUN_DIR, "raw", key.replace("/", "__") + ".json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _append_provenance(entry):
    path = os.path.join(RUN_DIR, "seeded_generation_provenance.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _batch_generation_pass_keys():
    path = os.path.join(RUN_DIR, "seeded_generation_provenance.jsonl")
    keys = set()
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if e.get("phase") == "generation" and \
                    e.get("channel") == "batch" and \
                    e.get("artifact_pass", False):
                key = "%s/%s" % (str(e["identity"]["lemma"]).strip().lower(),
                                 (str(e["identity"].get("pos")) or "")
                                 .strip().lower())
                keys.add(key)
    return sorted(keys)


def cmd_submit_a():
    _, index, identities, cfg = load_seeds()
    progress = load_progress()
    remaining = compute_remaining(identities, progress)
    state = load_state("a")
    if state:
        print("state_a exists (status=%s); refusing double submit"
              % state.get("status"))
        return
    prompt_text, prompt_hash = load_prompt()
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
    save_state("a", {
        "status": "running", "job_id": job_id, "input_gcs": uri,
        "output_gcs": out_prefix, "submitted": submitted,
        "input_hash": in_hash, "prompt_hash": prompt_hash,
        "model": cfg["model_id"], "created_at": utc_now()})
    print("Batch A submitted: %d requests, job %s" % (len(reqs), job_id))


def cmd_poll_a(wait_minutes=0):
    cfg = load_config()
    state = load_state("a")
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
        time.sleep(20)
        job = client.batches.get(name=state["job_id"])
        print("job state: %s" % getattr(job, "state", "?"))
    if _job_failed(job):
        state["status"] = "failed"
        state["error"] = str(getattr(job, "error", ""))
        save_state("a", state)
        print("BATCH A FAILED: %s" % state["error"])
        return
    _, index, _identities, _cfg = load_seeds()
    submitted_map = {s["key"].replace("/", "__"): s for s in
                     state["submitted"]}
    lines = _download_output_lines(state["output_gcs"],
                                   os.path.join(BATCH_SUBDIR, "outputs_a"))
    outcomes = import_generation_records(
        lines, submitted_map, index, state["prompt_hash"], state["model"],
        {"job_id": state["job_id"], "input_gcs": state["input_gcs"],
         "output_gcs": state["output_gcs"]})
    progress = load_progress()
    imported = 0
    passed = 0
    failed = 0
    for key, entry, err, artifact_pass, candidate, arm in outcomes:
        if key is None:
            failed += 1
            continue
        if entry is None:
            progress.setdefault("items", {})[key] = {
                "status": "error", "message": err}
            failed += 1
            continue
        with open(os.path.join(RUN_DIR, "raw",
                               key.replace("/", "__") + ".json"),
                  "w", encoding="utf-8") as f:
            json.dump({"identity": entry["identity"],
                       "candidate": candidate,
                       "arm": arm},
                      f, ensure_ascii=False, indent=1)
        _append_provenance(entry)
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
    save_state("a", state)
    print("Batch A imported: %d lines, %d mapped, %d pass, %d fail/err"
          % (len(lines), imported, passed, failed))


def cmd_submit_b():
    cfg = load_config()
    state = load_state("b")
    if state:
        print("state_b exists (status=%s); refusing double submit"
              % state.get("status"))
        return
    _, index, _identities, _cfg = load_seeds()
    batch_gen_keys = _batch_generation_pass_keys()
    pass_keys = []
    for key in batch_gen_keys:
        if key not in index:
            raise RuntimeError("batch generation key %s missing from index"
                               % key)
        pass_keys.append(key)
    reqs = build_decision_requests(pass_keys, index, _load_raw)
    os.makedirs(BATCH_SUBDIR, exist_ok=True)
    req_path = os.path.join(BATCH_SUBDIR, "requests_b.jsonl")
    with open(req_path, "w", encoding="utf-8") as f:
        for req in reqs:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")
    in_hash = _file_hash(req_path)
    blob_name = "%s/input_b/requests.jsonl" % GCS_RUN_PREFIX
    uri = _upload(req_path, blob_name)
    out_prefix = "gs://%s/%s/output_b" % (BUCKET, GCS_RUN_PREFIX)
    client = _client(cfg)
    job = client.batches.create(
        model=cfg["model_id"], src=uri,
        config=CreateBatchJobConfig(dest=out_prefix))
    job_id = getattr(job, "name", str(job))
    submitted = [{"key": key, "lemma": index[key]["lemma"],
                  "pos": index[key].get("pos"),
                  "cefr": index[key]["seed"].get("cefr")}
                 for key in pass_keys]
    save_state("b", {
        "status": "running", "job_id": job_id, "input_gcs": uri,
        "output_gcs": out_prefix, "submitted": submitted,
        "input_hash": in_hash, "model": cfg["model_id"],
        "created_at": utc_now()})
    print("Batch B submitted: %d requests, job %s" % (len(reqs), job_id))


def cmd_poll_b(wait_minutes=0):
    cfg = load_config()
    state = load_state("b")
    if not state:
        print("no state_b; run submit-b first")
        return
    if state.get("status") == "imported":
        print("state_b already imported (%d submitted)"
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
        time.sleep(20)
        job = client.batches.get(name=state["job_id"])
        print("job state: %s" % getattr(job, "state", "?"))
    if _job_failed(job):
        state["status"] = "failed"
        state["error"] = str(getattr(job, "error", ""))
        save_state("b", state)
        print("BATCH B FAILED: %s" % state["error"])
        return
    _, index, _identities, _cfg = load_seeds()
    submitted_map = {s["key"].replace("/", "__"): s for s in
                     state["submitted"]}
    lines = _download_output_lines(state["output_gcs"],
                                   os.path.join(BATCH_SUBDIR, "outputs_b"))
    outcomes = import_decision_records(
        lines, submitted_map, index, state["model"],
        {"job_id": state["job_id"]})
    progress = load_progress()
    imported = 0
    ok = 0
    for key, entry, err in outcomes:
        if key is None or entry is None:
            continue
        _append_provenance(entry)
        imported += 1
        if entry["decisions_status"] == "ok":
            ok += 1
        progress.setdefault("items", {})[key]["decisions_status"] = \
            entry["decisions_status"]
    save_progress(progress)
    state["status"] = "imported"
    state["imported_at"] = utc_now()
    save_state("b", state)
    print("Batch B imported: %d lines, %d mapped, %d decisions ok"
          % (len(lines), imported, ok))


def cmd_status():
    progress = load_progress()
    seeds, _index, identities, _cfg = load_seeds()
    by_status = {}
    by_pass = {}
    by_dec = {}
    for key, item in progress.get("items", {}).items():
        status = item.get("status")
        by_status[status] = by_status.get(status, 0) + 1
        if status == "success":
            ap = item.get("artifact_pass", False)
            by_pass["artifact_pass" if ap else "artifact_fail"] = \
                by_pass.get("artifact_pass" if ap else "artifact_fail", 0) + 1
            ds = item.get("decisions_status")
            if ds:
                by_dec[ds] = by_dec.get(ds, 0) + 1
    prov_path = os.path.join(RUN_DIR, "seeded_generation_provenance.jsonl")
    phases = {}
    if os.path.exists(prov_path):
        with open(prov_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                e = json.loads(line)
                phase = e.get("phase", "combined_online")
                phases[phase] = phases.get(phase, 0) + 1
    print("total snapshots: %d" % len(seeds))
    print("progress items: %d" % len(progress.get("items", {})))
    print("by status:", by_status)
    print("by artifact:", by_pass)
    print("by decisions:", by_dec)
    print("provenance phases:", phases)
    for phase in ("a", "b"):
        st = load_state(phase)
        if st:
            print("state_%s: status=%s job=%s submitted=%d" %
                  (phase, st.get("status"), st.get("job_id"),
                   len(st.get("submitted", []))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["submit-a", "poll-a", "submit-b",
                                        "poll-b", "status"])
    parser.add_argument("--wait-minutes", type=int, default=0)
    args = parser.parse_args()
    if args.cmd == "submit-a":
        cmd_submit_a()
    elif args.cmd == "poll-a":
        cmd_poll_a(args.wait_minutes)
    elif args.cmd == "submit-b":
        cmd_submit_b()
    elif args.cmd == "poll-b":
        cmd_poll_b(args.wait_minutes)
    elif args.cmd == "status":
        cmd_status()


if __name__ == "__main__":
    main()