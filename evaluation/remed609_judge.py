"""Batch transport driver for the Ticket-19 609 blind judge.

Single-phase batch (frozen pattern from the 348 judge run): every eval_id
is pre-audited inside the eval_remed609_v1 package; the judge ONLY
adjudicates A/B arms. Frozen pins live in evaluation.seeded_judge
(build_requests) and evaluation.ai_judge (build_judge_prompt):
temperature 0.0, maxOutputTokens 4000, responseMimeType application/json,
thinkingLevel low, location global, model gemini-3.8-flash.

Usage:
  GOOGLE_APPLICATION_CREDENTIALS=<key> python -m evaluation.remed609_judge submit
  GOOGLE_APPLICATION_CREDENTIALS=<key> python -m evaluation.remed609_judge poll --wait-minutes 60
  GOOGLE_APPLICATION_CREDENTIALS=<key> python -m evaluation.remed609_judge status
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
    _file_hash,
    _job_failed,
    _job_succeeded,
    _upload,
    load_config,
)
from evaluation.seeded_judge import build_requests, import_ballots, save_ballots
from evaluation.utils import utc_now
from google.cloud import storage
from google.genai.types import CreateBatchJobConfig

BUCKET = "lexical-enrichment"
GCS_PREFIX = "seeded609/eval-remed609/judge"
BASE = os.path.join(ROOT_DIR, ".scratch", "lexical-migration-build", "output")
PKG_DIR = os.path.join(BASE, "eval_remed609_v1")
WORK_DIR = os.path.join(PKG_DIR, "judge_batch")


def _req_path():
    return os.path.join(WORK_DIR, "requests.jsonl")


def _state_path():
    return os.path.join(WORK_DIR, "state.json")


def load_state():
    if os.path.exists(_state_path()):
        with open(_state_path(), encoding="utf-8") as f:
            return json.load(f)
    return None


def save_state(state):
    os.makedirs(WORK_DIR, exist_ok=True)
    with open(_state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def cmd_submit():
    if load_state():
        print("judge state exists; refusing double submit")
        return
    cfg = load_config()
    with open(os.path.join(PKG_DIR, "eval_remed609_v1.json"),
              encoding="utf-8") as f:
        items = json.load(f)["items"]
    reqs = build_requests(items)
    # Transport conformance (attempt-1 failed server-side for ALL 590 with
    # status code 3 "Please use a valid role: user, model"): the frozen
    # builder emits role-less contents, which the batch endpoint now rejects
    # (the 348 run predates this validation; generation requests already
    # carry role:user and succeed). Inject role:user into the ENVELOPE ONLY —
    # prompt bytes (frozen rubric) untouched; proven by a single online probe
    # returning a parseable ballot. Frozen module NOT modified.
    for req in reqs:
        req["request"]["contents"] = [
            {"role": "user", "parts": c.get("parts", [])}
            for c in req["request"]["contents"]]
    os.makedirs(WORK_DIR, exist_ok=True)
    with open(_req_path(), "w", encoding="utf-8") as f:
        for req in reqs:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")
    in_hash = _file_hash(_req_path())
    uri = _upload(_req_path(), "%s/input/requests.jsonl" % GCS_PREFIX)
    out_prefix = "gs://%s/%s/output" % (BUCKET, GCS_PREFIX)
    client = _client(cfg)
    job = client.batches.create(
        model="gemini-3.8-flash", src=uri,
        config=CreateBatchJobConfig(dest=out_prefix))
    job_id = getattr(job, "name", str(job))
    save_state({
        "status": "running", "job_id": job_id, "input_gcs": uri,
        "output_gcs": out_prefix, "n_requests": len(reqs),
        "input_hash": in_hash, "model": "gemini-3.8-flash",
        "created_at": utc_now()})
    print("Judge batch submitted: %d requests, job %s" % (len(reqs), job_id))


def _download_lines(output_gcs, local_dir):
    """Local mirror of seeded_batch._download_output_lines, except sorting
    by blob NAME: the installed storage client version made Blob objects
    unorderable, so sorted() over 2+ blobs crashes (generation output had a
    single blob, which is why 609-A imported fine). Same file selection
    (.jsonl), same concatenation order (by name), same return shape."""
    prefix = output_gcs.replace("gs://", "").split("/", 1)[1]
    os.makedirs(local_dir, exist_ok=True)
    sc = storage.Client()
    bucket = sc.bucket(BUCKET)
    lines = []
    for blob in sorted(bucket.list_blobs(prefix=prefix),
                       key=lambda b: b.name):
        if not blob.name.endswith(".jsonl"):
            continue
        local = os.path.join(local_dir, os.path.basename(blob.name))
        blob.download_to_filename(local)
        with open(local, encoding="utf-8") as f:
            lines.extend(f.readlines())
    return lines


def cmd_poll(wait_minutes=0):
    cfg = load_config()
    state = load_state()
    if not state:
        print("no judge state; run submit first")
        return
    if state.get("status") == "imported":
        print("judge already imported (%d requests)" % state["n_requests"])
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
        print("JUDGE BATCH FAILED: %s" % state["error"])
        return
    with open(os.path.join(PKG_DIR, "eval_remed609_v1.json"),
              encoding="utf-8") as f:
        eval_ids = [i["eval_id"] for i in json.load(f)["items"]]
    lines = _download_lines(state["output_gcs"],
                              os.path.join(WORK_DIR, "outputs"))
    judgments, rejects, malformed = import_ballots(lines, eval_ids)
    out_path = os.path.join(PKG_DIR, "ballots.json")
    save_ballots(judgments, rejects, malformed, out_path)
    state["status"] = "imported"
    state["imported_at"] = utc_now()
    state["n_judged"] = len(judgments)
    state["n_rejects"] = len(rejects)
    state["n_malformed"] = malformed
    save_state(state)
    print("Judge imported: %d judged, %d rejects, %d malformed"
          % (len(judgments), len(rejects), malformed))


def cmd_status():
    state = load_state()
    print(("judge: status=%s job=%s n=%s" % (
        state.get("status"), state.get("job_id"), state.get("n_requests"))
        if state else "judge: none"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["submit", "poll", "status"])
    parser.add_argument("--wait-minutes", type=int, default=0)
    args = parser.parse_args()
    if args.cmd == "submit":
        cmd_submit()
    elif args.cmd == "poll":
        cmd_poll(args.wait_minutes)
    elif args.cmd == "status":
        cmd_status()


if __name__ == "__main__":
    main()
