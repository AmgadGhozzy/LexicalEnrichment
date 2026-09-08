import os
import json
import argparse

from evaluation.utils import (
    EXPERIMENTS_DIR, GOLDEN_SET_DIR, load_json, write_json, utc_now, canonical_hash
)

def import_batch_output(experiment_id):
    exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    manifest_path = os.path.join(exp_dir, "manifest.json")
    
    if not os.path.exists(manifest_path):
        raise RuntimeError(f"Manifest not found at {manifest_path}")
        
    manifest = load_json(manifest_path)
    expected_count = manifest.get("progress", {}).get("total", 160)
    
    out_dir = os.path.join(exp_dir, "output")
    if not os.path.exists(out_dir):
        raise RuntimeError(f"Output directory {out_dir} not found. Run inspector first.")
        
    golden_set_path = os.path.join(GOLDEN_SET_DIR, "golden_v2.json")
    golden_data = load_json(golden_set_path)
    golden_map = {f"{experiment_id}-CAND-{entry['id']}": entry for entry in golden_data}
    
    raw_dir = os.path.join(exp_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    
    all_lines = []
    for f in os.listdir(out_dir):
        if f.endswith(".jsonl"):
            with open(os.path.join(out_dir, f), "r", encoding="utf-8") as f_in:
                all_lines.extend(f_in.readlines())
                
    accounting = {
        "expected": expected_count,
        "mapped": 0,
        "successful": 0,
        "failed": 0,
        "missing": 0,
        "duplicate_outputs": 0,
        "unknown_outputs": 0,
        "malformed_outputs": 0
    }
    
    processed_candidates = set()
    
    # 1st Pass: Audit
    for line in all_lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            accounting["malformed_outputs"] += 1
            continue
            
        cand_id = record.get("key") # Using official Gemini Batch 'key' field
        if not cand_id:
            accounting["unknown_outputs"] += 1
            continue
            
        if cand_id not in golden_map:
            accounting["unknown_outputs"] += 1
            continue
            
        if cand_id in processed_candidates:
            accounting["duplicate_outputs"] += 1
            continue
            
        processed_candidates.add(cand_id)
        accounting["mapped"] += 1
        
        # Categorize success vs failed based on Vertex API envelope
        if "error" in record:
            accounting["failed"] += 1
        else:
            accounting["successful"] += 1
            
    accounting["missing"] = expected_count - accounting["mapped"]
    
    print("Batch Importer Accounting:")
    print(json.dumps(accounting, indent=2))
    
    if accounting["missing"] > 0 or accounting["duplicate_outputs"] > 0 or accounting["unknown_outputs"] > 0 or accounting["malformed_outputs"] > 0:
        raise RuntimeError("CRITICAL MAPPING ERROR: Strict 1:1 mapping failed. Aborting import.")
        
    # 2nd Pass: Final Artifact Generation
    for line in all_lines:
        record = json.loads(line)
        cand_id = record["key"]
        entry = golden_map[cand_id]
        
        status = "failed"
        generated_data = None
        error_info = None
        
        if "error" in record:
            error_info = {"type": "BatchAPIError", "message": str(record["error"])}
        elif "response" in record:
            try:
                candidates = record["response"].get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text_resp = parts[0].get("text", "")
                        generated_data = json.loads(text_resp)
                        status = "success"
                    else:
                        error_info = {"type": "MissingParts", "message": "No parts in response"}
                else:
                    error_info = {"type": "NoCandidates", "message": "No candidates in response"}
            except json.JSONDecodeError as e:
                error_info = {"type": "JSONDecodeError", "message": str(e)}
            except Exception as e:
                error_info = {"type": "ParseError", "message": str(e)}
        else:
            error_info = {"type": "UnknownShape", "message": "Neither response nor error in envelope"}
            
        input_snapshot = {
            "lexical_id": entry['id'],
            "lemma": entry['wordEn'],
            "pos": entry['pos'],
            "cefr": entry['cefrLevel']
        }
        
        artifact = {
            "candidate_id": cand_id,
            "experiment_id": experiment_id,
            "lexical_entry": input_snapshot,
            "output": generated_data,
            "runtime": {
                "status": status,
                "generated_at": utc_now(),
                "latency_ms": 0,
                "attempt": 1,
                "error": error_info,
                "execution_backend": "batch"
            },
            "provenance": {
                "golden_set_id": manifest['golden_set_id'],
                "golden_set_hash": manifest['golden_set_hash'],
                "prompt_id": manifest['prompt_id'],
                "prompt_version": manifest['prompt_version'],
                "schema_version": manifest['schema_version'],
                "output_hash": canonical_hash(generated_data) if generated_data else None
            }
        }
        
        out_file = os.path.join(raw_dir, f"{cand_id}.json")
        write_json(out_file, artifact)
        
    print(f"Successfully imported {accounting['mapped']} artifacts into {raw_dir}")
    
    manifest["status"] = "completed"
    manifest["progress"]["completed"] = accounting["successful"]
    manifest["progress"]["failed"] = accounting["failed"]
    manifest["updated_at"] = utc_now()
    write_json(manifest_path, manifest)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True, help="Experiment ID to import")
    args = parser.parse_args()
    import_batch_output(args.experiment)
