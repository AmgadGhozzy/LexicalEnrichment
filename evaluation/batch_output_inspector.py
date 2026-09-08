import os
import json
import argparse
from collections import Counter

from evaluation.utils import (
    EXPERIMENTS_DIR, load_json, write_json
)
from google.cloud import storage

def inspect_batch_output(experiment_id):
    exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    manifest_path = os.path.join(exp_dir, "manifest.json")
    
    if not os.path.exists(manifest_path):
        raise RuntimeError(f"Manifest not found at {manifest_path}")
        
    manifest = load_json(manifest_path)
    if "batch_job" not in manifest:
        raise RuntimeError("No batch_job section in manifest.")
        
    output_prefix = manifest["batch_job"]["output_gcs_prefix"]
    
    bucket_name = output_prefix.replace("gs://", "").split("/")[0]
    prefix = "/".join(output_prefix.replace("gs://", "").split("/")[1:])
    
    job_id_parts = manifest["batch_job"]["job_id"].split("/")
    project_id = None
    if len(job_id_parts) > 2 and job_id_parts[0] == "projects":
        project_id = job_id_parts[1]
    
    storage_client = storage.Client(project=project_id) if project_id else storage.Client()
    bucket = storage_client.bucket(bucket_name)
    
    blobs = list(bucket.list_blobs(prefix=prefix))
    jsonl_blobs = [b for b in blobs if b.name.endswith(".jsonl")]
    
    if not jsonl_blobs:
        print("No JSONL output blobs found yet. Batch job may not be complete.")
        return
        
    out_dir = os.path.join(exp_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    
    inspection_dir = os.path.join(exp_dir, "inspection")
    os.makedirs(inspection_dir, exist_ok=True)
    
    all_lines = []
    for b in jsonl_blobs:
        local_path = os.path.join(out_dir, os.path.basename(b.name))
        b.download_to_filename(local_path)
        with open(local_path, "r", encoding="utf-8") as f:
            all_lines.extend(f.readlines())
            
    expected_count = manifest.get("progress", {}).get("total", 160)
    print(f"Downloaded {len(all_lines)} total output lines.")
    
    report = {
        "line_count": len(all_lines),
        "expected_count": expected_count,
        "count_matches_expected": (len(all_lines) == expected_count),
        "malformed_json_lines": 0,
        "top_level_key_frequency": {},
        "keys_presence": {
            "key": 0,
            "request": 0,
            "response": 0,
            "error": 0
        },
        "duplicate_keys": 0,
        "unknown_keys": 0,
        "missing_keys": 0
    }
    
    seen_keys = set()
    
    for line in all_lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            report["malformed_json_lines"] += 1
            continue
            
        keys_tuple = tuple(sorted(record.keys()))
        report["top_level_key_frequency"][str(keys_tuple)] = report["top_level_key_frequency"].get(str(keys_tuple), 0) + 1
        
        # Use official 'key' field for Gemini Batch
        cand_key = record.get("key")
        if cand_key:
            report["keys_presence"]["key"] += 1
            if cand_key in seen_keys:
                report["duplicate_keys"] += 1
            seen_keys.add(cand_key)
        else:
            report["missing_keys"] += 1
            
        if "request" in record:
            report["keys_presence"]["request"] += 1
        if "response" in record:
            report["keys_presence"]["response"] += 1
        if "error" in record:
            report["keys_presence"]["error"] += 1
            
    report_file = os.path.join(inspection_dir, "output_envelope.json")
    write_json(report_file, report)
    print(f"Inspection report written to {report_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True, help="Experiment ID to inspect")
    args = parser.parse_args()
    inspect_batch_output(args.experiment)
