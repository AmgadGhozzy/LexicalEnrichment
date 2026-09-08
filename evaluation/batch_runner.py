import os
import json
import argparse

from google import genai
from google.genai.types import CreateBatchJobConfig
from google.cloud import storage

from evaluation.utils import (
    EXPERIMENTS_DIR, CONFIGS_DIR, GOLDEN_SET_DIR,
    utc_now, load_json, write_json, get_file_hash,
    generate_experiment_id, get_sdk_version
)
from evaluation.batch_input_builder import build_batch_input

def run_batch(config_file):
    config_path = os.path.join(CONFIGS_DIR, config_file)
    if not os.path.exists(config_path):
        raise RuntimeError(f"Config file {config_path} not found.")

    config = load_json(config_path)
    
    exp_id = generate_experiment_id()
    exp_dir = os.path.join(EXPERIMENTS_DIR, exp_id)
    os.makedirs(exp_dir, exist_ok=True)
    
    print(f"Starting batch runner for {exp_id}...")
    
    # 1. Build Batch Input
    input_file, input_hash = build_batch_input(config_file, exp_id)

    total_requests = 0
    with open(input_file, 'r', encoding='utf-8') as _f:
        for _line in _f:
            if _line.strip():
                total_requests += 1
    
    # 2. Upload to GCS
    bucket_name = config["batch"]["bucket"]
    input_prefix = config["batch"]["input_prefix"].format(experiment_id=exp_id)
    output_prefix = config["batch"]["output_prefix"].format(experiment_id=exp_id)
    input_blob_name = f"{input_prefix}{config['batch']['input_jsonl_filename']}"
    
    gcs_input_uri = f"gs://{bucket_name}/{input_blob_name}"
    gcs_output_uri = f"gs://{bucket_name}/{output_prefix}"
    
    storage_client = storage.Client(project=config.get("project_id"))
    bucket = storage_client.bucket(bucket_name)
    
    blob = bucket.blob(input_blob_name)
    blob.upload_from_filename(input_file)
    print(f"Uploaded input to {gcs_input_uri}")
    
    # 3. Submit Batch Job
    project_id = config.get("project_id") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise RuntimeError("GCP project_id is not configured.")
        
    location = config.get("location", "us-central1")
    
    from google.genai.types import HttpOptions
    client = genai.Client(
        vertexai=True, 
        project=project_id, 
        location=location,
        http_options=HttpOptions(api_version="v1")
    )
    
    print(f"Creating Batch Job on Vertex AI ({location})...")
    # Exact GenAI API call as per latest SDK
    job = client.batches.create(
        model=config['model_id'],
        src=gcs_input_uri,
        config=CreateBatchJobConfig(
            dest=gcs_output_uri
        )
    )
    
    job_id = getattr(job, "name", str(job))
    print(f"Batch Job Created: {job_id}")
    
    # 4. Write Manifest
    manifest_path = os.path.join(exp_dir, "manifest.json")
    
    manifest = {
        "experiment_id": exp_id,
        "execution_backend": "batch",
        "experiment_type": "batch_pilot",
        "status": "running",
        "schema_version": config['schema_version'],
        "prompt_id": config['prompt_id'],
        "prompt_version": config['prompt_version'],
        "model_provider": "google",
        "model_id": config['model_id'],
        "model_version": None,
        "sdk": {
            "package": "google-genai",
            "version": get_sdk_version()
        },
        "thinking_mode": config.get('thinking', {"enabled": False}),
        "grounding": config.get('grounding', {"enabled": False, "provider": None}),
        "generation_config": {
            "temperature": config.get('temperature'),
            "top_p": config.get('top_p'),
            "top_k": config.get('top_k'),
            "max_output_tokens": config.get('max_output_tokens')
        },
        "golden_set_id": "golden_v2", 
        "golden_set_hash": get_file_hash(os.path.join(GOLDEN_SET_DIR, "golden_v2.json")), 
        "batch_job": {
            "job_id": job_id,
            "input_gcs_uri": gcs_input_uri,
            "output_gcs_prefix": gcs_output_uri,
            "input_jsonl_sha256": input_hash
        },
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "progress": {
            "total": total_requests,
            "completed": 0,
            "failed": 0,
            "skipped": 0
        }
    }
    
    write_json(manifest_path, manifest)
    print(f"Manifest written to {manifest_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Config file name in evaluation/configs")
    args = parser.parse_args()
    
    run_batch(args.config)
