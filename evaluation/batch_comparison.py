import os
import json
import argparse

from evaluation.utils import (
    EXPERIMENTS_DIR, load_json
)

def compare_experiments(online_id, batch_id):
    online_report_path = os.path.join(EXPERIMENTS_DIR, online_id, "validation", "report.json")
    batch_report_path = os.path.join(EXPERIMENTS_DIR, batch_id, "validation", "report.json")
    
    if not os.path.exists(online_report_path):
        raise RuntimeError(f"Online report not found: {online_report_path}")
    if not os.path.exists(batch_report_path):
        raise RuntimeError(f"Batch report not found: {batch_report_path}")
        
    online = load_json(online_report_path)
    batch = load_json(batch_report_path)
    
    print("========================================")
    print("       BATCH VS ONLINE COMPARISON       ")
    print("========================================")
    print(f"Online Experiment : {online_id}")
    print(f"Batch Experiment  : {batch_id}")
    print("----------------------------------------")
    
    metrics = [
        "total_expected",
        "generated",
        "missing",
        "malformed_json",
        "validator_pass",
        "validator_flag",
        "validator_fail",
        "target_word_missing",
        "schema_failures",
        "hash_failures"
    ]
    
    online_metrics = online.get("summary", {})
    batch_metrics = batch.get("summary", {})
    
    print(f"{'Metric':<25} | {'Online':<10} | {'Batch':<10} | {'Diff'}")
    print("-" * 65)
    
    for m in metrics:
        o_val = online_metrics.get(m, 0)
        b_val = batch_metrics.get(m, 0)
        diff = b_val - o_val
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        if diff == 0:
            diff_str = "-"
        print(f"{m:<25} | {o_val:<10} | {b_val:<10} | {diff_str}")
        
    print("========================================")
    print("Candidate-Level Matches")
    print("----------------------------------------")
    # Compare candidate outputs (hash level)
    online_details = online.get("details", [])
    batch_details = batch.get("details", [])
    
    online_map = {d["candidate_id"].split("-CAND-")[-1]: d for d in online_details}
    batch_map = {d["candidate_id"].split("-CAND-")[-1]: d for d in batch_details}
    
    identical_outputs = 0
    different_outputs = 0
    
    for lex_id, o_det in online_map.items():
        if lex_id in batch_map:
            b_det = batch_map[lex_id]
            # If both generated JSON, compare the JSON
            if o_det.get("status") == "PASS" and b_det.get("status") == "PASS":
                # Assuming the outputs are largely deterministic, but we can't guarantee exact hash match 
                # for LLMs at temperature 0.2. But we can compare status.
                if o_det["status"] == b_det["status"]:
                    identical_outputs += 1
                else:
                    different_outputs += 1
            else:
                if o_det["status"] == b_det["status"]:
                    identical_outputs += 1
                else:
                    different_outputs += 1
                    
    print(f"Candidates with identical validation status: {identical_outputs}")
    print(f"Candidates with different validation status: {different_outputs}")
    print("========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", required=True, help="Online experiment ID (e.g. EXP-2026-09-02-012)")
    parser.add_argument("--batch", required=True, help="Batch experiment ID")
    args = parser.parse_args()
    
    compare_experiments(args.online, args.batch)
