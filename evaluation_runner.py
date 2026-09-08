import os
import json
import time

# Using standard Vertex genai Python SDK
from google import genai
from google.genai.types import HttpOptions
from google.genai import types
from google.genai import errors

# Project Paths
from evaluation.utils import (
    ROOT_DIR, EVAL_DIR, GOLDEN_SET_DIR, EXPERIMENTS_DIR, CONFIGS_DIR, PROMPTS_DIR, SCHEMAS_DIR,
    utc_now, canonical_hash, get_file_hash, load_json, write_json,
    generate_experiment_id, get_sdk_version
)

# ---------------------------------------------------------
# Core Utilities
# ---------------------------------------------------------
def ensure_dirs():
    os.makedirs(EXPERIMENTS_DIR, exist_ok=True)
    os.makedirs(CONFIGS_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    os.makedirs(SCHEMAS_DIR, exist_ok=True)
    os.makedirs(os.path.join(EVAL_DIR, "validation"), exist_ok=True)
    os.makedirs(os.path.join(EVAL_DIR, "blind"), exist_ok=True)
    os.makedirs(os.path.join(EVAL_DIR, "reports"), exist_ok=True)

# ---------------------------------------------------------
# Smoke Test Stratification
# ---------------------------------------------------------
def select_smoke_entries(data, max_n=5):
    """Deterministic selection of stratified entries for smoke tests."""
    strata = {}
    for entry in data:
        strata.setdefault(entry.get("stratum", "unknown"), []).append(entry)
    
    selected = []
    # Pick one from each bucket until we hit max_n
    for bucket in sorted(strata.keys()):
        if len(selected) >= max_n:
            break
        selected.append(strata[bucket][0])
    return selected

# ---------------------------------------------------------
# Experiment Execution
# ---------------------------------------------------------
def run_experiment(config_file, smoke_test=True, resume_id=None):
    ensure_dirs()
    config_path = os.path.join(CONFIGS_DIR, config_file)
    if not os.path.exists(config_path):
        print(f"Error: Config file {config_path} not found.")
        return

    config = load_json(config_path)
    
    # 1. Gate 8A.1: Golden Set Integrity
    golden_set_path = os.path.join(GOLDEN_SET_DIR, "golden_v2.json")
    manifest_path = os.path.join(GOLDEN_SET_DIR, "manifest.json")
    
    golden_manifest = load_json(manifest_path)
    actual_golden_hash = get_file_hash(golden_set_path)
    declared_hash = golden_manifest.get("golden_set_sha256")
    
    if actual_golden_hash != declared_hash:
        raise RuntimeError(f"Golden Set hash mismatch! Manifest: {declared_hash}, Actual: {actual_golden_hash}")
        
    golden_data = load_json(golden_set_path)
    if len(golden_data) != golden_manifest.get("entry_count", 160):
        raise RuntimeError("Golden Set entry count mismatch.")
        
    if smoke_test:
        # Check if explicit IDs are provided for the smoke test
        if "smoke_test_ids" in config:
            requested_ids = config["smoke_test_ids"]
            available = {d["id"]: d for d in golden_data}
            missing_ids = [x for x in requested_ids if x not in available]
            if missing_ids:
                raise RuntimeError(f"Smoke test IDs not found in Golden Set: {missing_ids}")
            if len(requested_ids) != len(set(requested_ids)):
                raise RuntimeError("Duplicate smoke_test_ids detected.")
            golden_data = [available[x] for x in requested_ids]
            if not golden_data:
                raise RuntimeError("Smoke test resolved to zero entries.")
        else:
            golden_data = select_smoke_entries(golden_data, max_n=5)
            
        print(f"SMOKE TEST MODE: Running on {len(golden_data)} stratified lexical entries.")
        
    # 2. Gate 8A.2: Prompt & Schema
    prompt_path = os.path.join(PROMPTS_DIR, f"{config['prompt_id']}.txt")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    prompt_hash = get_file_hash(prompt_path)

    schema_path = os.path.join(SCHEMAS_DIR, f"{config['schema_version']}.json")
    output_schema = load_json(schema_path)

    # 3. Gate 8A.3: Vertex Client
    # Uses ADC, project/location from config or environment
    project_id = config.get("project_id", os.environ.get("GOOGLE_CLOUD_PROJECT"))
    location = config.get("location", "us-central1")
    
    client = genai.Client(
        vertexai=True, 
        project=project_id, 
        location=location,
        http_options=HttpOptions(api_version="v1")
    )
    
    # 4. Initialize Experiment Directory & Manifest
    if resume_id:
        exp_id = resume_id
        exp_dir = os.path.join(EXPERIMENTS_DIR, exp_id)
        if not os.path.exists(exp_dir):
            raise RuntimeError(f"Cannot resume: {exp_dir} does not exist.")
        raw_dir = os.path.join(exp_dir, "raw")
        err_dir = os.path.join(exp_dir, "errors")
    else:
        exp_id = generate_experiment_id()
        exp_dir = os.path.join(EXPERIMENTS_DIR, exp_id)
        raw_dir = os.path.join(exp_dir, "raw")
        err_dir = os.path.join(exp_dir, "errors")
        os.makedirs(raw_dir)
        os.makedirs(err_dir)

    thinking_config = config.get('thinking', {"enabled": False})
    if thinking_config.get("enabled", False):
        # We enforce that thinking is NOT recorded as enabled unless explicitly supported and passed
        raise RuntimeError("Thinking is enabled in config but not implemented by this runner version.")
        
    generation_config_dict = {
        "temperature": config.get('temperature', 0.2),
        "top_p": config.get('top_p', None),
        "top_k": config.get('top_k', None),
        "max_output_tokens": config.get('max_output_tokens', 1024)
    }
    if "seed" in config:
        generation_config_dict["seed"] = config["seed"]
        
    manifest_path_exp = os.path.join(exp_dir, "manifest.json")
    if resume_id:
        if not os.path.exists(manifest_path_exp):
            raise RuntimeError(f"Cannot resume: {manifest_path_exp} does not exist.")
        exp_manifest = load_json(manifest_path_exp)
        
        # Config compatibility lock
        mismatches = []
        if exp_manifest.get('model_id') != config.get('model_id'): mismatches.append("model_id")
        if exp_manifest.get('prompt_id') != config.get('prompt_id'): mismatches.append("prompt_id")
        if exp_manifest.get('prompt_version') != config.get('prompt_version'): mismatches.append("prompt_version")
        if exp_manifest.get('schema_version') != config.get('schema_version'): mismatches.append("schema_version")
        if exp_manifest.get('thinking_mode') != thinking_config: mismatches.append("thinking_mode")
        if exp_manifest.get('generation_config') != generation_config_dict: mismatches.append("generation_config")
        
        if mismatches:
            raise RuntimeError(f"Resume configuration does not match experiment manifest in fields: {', '.join(mismatches)}")
            
        exp_manifest["status"] = "running"
        exp_manifest["progress"]["total"] = len(golden_data)
    else:
        exp_manifest = {
            "experiment_id": exp_id,
            "status": "running",
            "schema_version": config['schema_version'],
            "prompt_id": config['prompt_id'],
            "prompt_version": config['prompt_version'],
            "model_provider": "google",
            "model_id": config['model_id'],
            "model_version": None, # Will extract from response if possible
            "sdk": {
                "package": "google-genai",
                "version": get_sdk_version()
            },
            "thinking_mode": thinking_config,
            "grounding": config.get('grounding', {"enabled": False, "provider": None}),
            "generation_config": generation_config_dict,
            "golden_set_id": golden_manifest['golden_set_id'],
            "golden_set_hash": actual_golden_hash,
            "started_at": utc_now(),
            "completed_at": None,
            "progress": {
                "total": len(golden_data),
                "completed": 0,
                "failed": 0,
                "skipped": 0
            }
        }
    
    write_json(manifest_path_exp, exp_manifest)

    print(f"Started {exp_id} with {config['model_id']}...")
    
    # Configure request
    gen_config_kwargs = {
        "temperature": exp_manifest['generation_config']['temperature'],
        "top_p": exp_manifest['generation_config']['top_p'],
        "top_k": exp_manifest['generation_config']['top_k'],
        "max_output_tokens": exp_manifest['generation_config']['max_output_tokens'],
        "response_mime_type": "application/json",
        "response_schema": output_schema
    }
    if "seed" in exp_manifest['generation_config']:
        gen_config_kwargs["seed"] = exp_manifest['generation_config']['seed']
        
    gen_config = types.GenerateContentConfig(**gen_config_kwargs)
    
    if exp_manifest['grounding'].get('enabled'):
        if exp_manifest['grounding'].get('provider') == 'google_search':
            gen_config.tools = [types.Tool(google_search=types.GoogleSearch())]
            
    # Generation Loop
    for entry in golden_data:
        cand_id = f"{exp_id}-CAND-{entry['id']}"
        
        # Resume Check (No overwrite)
        out_file = os.path.join(raw_dir, f"{cand_id}.json")
        err_file = os.path.join(err_dir, f"{cand_id}.json")
        
        if os.path.exists(out_file) or os.path.exists(err_file):
            print(f"[SKIP_EXISTING] {cand_id}")
            # Existing artifacts are already accounted for in the loaded manifest's 'completed' or 'failed' count.
            continue
            
        # Prepare Inputs
        input_snapshot = {
            "lexical_id": entry['id'],
            "lemma": entry['wordEn'],
            "pos": entry['pos'],
            "cefr": entry['cefrLevel']
        }
        input_entry_hash = canonical_hash(input_snapshot)
        
        prompt_text = prompt_template.format(
            lemma=entry['wordEn'], 
            pos=entry['pos'], 
            cefr=entry['cefrLevel']
        )
        rendered_prompt_hash = canonical_hash(prompt_text)
        
        # Execution with Retries
        max_attempts = 3
        attempt = 0
        status = "failed"
        generated_data = None
        error_info = None
        latency_ms = 0
        
        while attempt < max_attempts:
            attempt += 1
            start_time = time.time()
            try:
                response = client.models.generate_content(
                    model=config['model_id'],
                    contents=prompt_text,
                    config=gen_config
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Try parsing JSON
                generated_data = json.loads(response.text)
                status = "success"
                
                # Attempt to extract exact model version if Vertex returns it
                if response.model_version and not exp_manifest['model_version']:
                    exp_manifest['model_version'] = response.model_version
                    
                break # Success
                
            except json.JSONDecodeError as e:
                # Schema failure - no retry makes sense without changing the prompt/model
                raw_text = getattr(response, "text", "<no text available>") if 'response' in locals() else "<no response>"
                error_info = {
                    "type": "JSONDecodeError", 
                    "message": str(e), 
                    "attempt": attempt,
                    "raw_response": raw_text
                }
                break 
            except errors.APIError as e:
                # API Error -> retry (e.g. rate limit, 503)
                error_info = {"type": "APIError", "message": str(e), "attempt": attempt}
                e_str = str(e)
                if ("429" in e_str or "503" in e_str or "500" in e_str or "504" in e_str) and attempt < max_attempts:
                    time.sleep(min(2 ** attempt, 30))
                else:
                    break
            except Exception as e:
                # Other exceptions -> log and abort retries
                error_info = {"type": type(e).__name__, "message": str(e), "attempt": attempt}
                break

        # Finalize Output
        out_hash = canonical_hash(generated_data) if generated_data else None
        
        artifact = {
            "candidate_id": cand_id,
            "experiment_id": exp_id,
            "lexical_entry": input_snapshot,
            "output": generated_data,
            "runtime": {
                "status": status,
                "generated_at": utc_now(),
                "latency_ms": latency_ms,
                "attempt": attempt,
                "error": error_info
            },
            "provenance": {
                "golden_set_id": exp_manifest['golden_set_id'],
                "golden_set_hash": actual_golden_hash,
                "input_entry_hash": input_entry_hash,
                "prompt_id": exp_manifest['prompt_id'],
                "prompt_version": exp_manifest['prompt_version'],
                "prompt_hash": prompt_hash,
                "rendered_prompt_hash": rendered_prompt_hash,
                "schema_version": exp_manifest['schema_version'],
                "output_hash": out_hash
            }
        }
        
        # Persist
        if status == "success":
            write_json(out_file, artifact)
            exp_manifest['progress']['completed'] += 1
            print(f"[SUCCESS] {cand_id} - {entry['wordEn']} ({latency_ms}ms) - Att: {attempt}")
        else:
            write_json(err_file, artifact)
            exp_manifest['progress']['failed'] += 1
            print(f"[FAILED] {cand_id} - {entry['wordEn']} - Error: {error_info['type']}")
            
        # Update manifest continuously
        write_json(manifest_path_exp, exp_manifest)
        
        # Configurable Rate Limit
        time.sleep(config.get('rate_limit_seconds', 1))

    # Complete Manifest
    exp_manifest['status'] = "completed" if exp_manifest['progress']['failed'] == 0 else "completed_with_errors"
    exp_manifest['completed_at'] = utc_now()
    write_json(manifest_path_exp, exp_manifest)
        
    print(f"\n[DONE] Experiment {exp_id} Finished.")
    print(json.dumps(exp_manifest['progress'], indent=2))

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Lexical Enrichment Evaluation")
    parser.add_argument("--config", required=True, help="Configuration JSON file in evaluation/configs/")
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke", help="Execution mode: smoke (default) or full")
    parser.add_argument("--resume", help="Experiment ID to resume (e.g. EXP-2026-09-02-010)")
    
    args = parser.parse_args()
    
    ensure_dirs()
    smoke_test = (args.mode == "smoke")
    run_experiment(args.config, smoke_test=smoke_test, resume_id=args.resume)
