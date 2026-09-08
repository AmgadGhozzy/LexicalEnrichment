import os
import sys
import json

from evaluation.utils import (
    EVAL_DIR, EXPERIMENTS_DIR, SCHEMAS_DIR,
    utc_now, canonical_hash, load_json, write_json
)
from evaluation.lexical_validator import (
    LexicalValidator,
    GENERIC_NULL_VALUES,
    convert_gemini_schema,
    normalize_token,
    tokenize,
    contains_target,
    is_circular_definition,
)

VALIDATOR_VERSION = "1.0.0"


def validate_artifact(artifact, exp_id, schema):
    """Compatibility wrapper over the canonical LexicalValidator.

    Existing callers keep this exact signature and behavior. The rule
    implementation lives in evaluation.lexical_validator.LexicalValidator.
    Diagnostics are preserved byte-for-byte.
    """
    return LexicalValidator().validate_artifact(artifact, exp_id, schema)


def main(exp_id):
    exp_dir = os.path.join(EXPERIMENTS_DIR, exp_id)
    raw_dir = os.path.join(exp_dir, "raw")
    manifest_path = os.path.join(exp_dir, "manifest.json")
    val_dir = os.path.join(exp_dir, "validation")
    
    if not os.path.exists(exp_dir) or not os.path.exists(raw_dir):
        print(f"Error: Experiment directory not found: {exp_dir}")
        sys.exit(2)
        
    if not os.path.exists(manifest_path):
        print(f"Error: manifest.json not found for experiment {exp_id}")
        sys.exit(2)
        
    os.makedirs(val_dir, exist_ok=True)
    
    manifest = load_json(manifest_path)
    schema_version = manifest.get("schema_version")
    if not schema_version:
        print("Error: schema_version not found in manifest")
        sys.exit(2)
        
    schema_path = os.path.join(SCHEMAS_DIR, f"{schema_version}.json")
    if not os.path.exists(schema_path):
        print(f"Error: Schema file not found: {schema_path}")
        sys.exit(2)
        
    gemini_schema = load_json(schema_path)
    std_schema = convert_gemini_schema(gemini_schema)
    
    # sorted() guarantees deterministic report ordering across platforms.
    # os.listdir() order is filesystem-dependent and non-reproducible.
    artifacts = sorted(f for f in os.listdir(raw_dir) if f.endswith(".json"))
    print(f"Experiment: {exp_id}")
    print(f"Validator: artifact_validator v{VALIDATOR_VERSION}")
    print(f"Artifacts found: {len(artifacts)}\n")
    
    report = {
        "experiment_id": exp_id,
        "validator_id": "artifact_validator",
        "validator_version": VALIDATOR_VERSION,
        "schema_version": schema_version,
        "validated_at": utc_now(),
        "summary": {
            "total": len(artifacts),
            "passed": 0,
            "failed": 0,
            "flagged": 0
        },
        "candidates": []
    }
    
    for filename in artifacts:
        filepath = os.path.join(raw_dir, filename)
        artifact = load_json(filepath)
        
        checks, failures, flags = validate_artifact(artifact, exp_id, std_schema)
        
        if failures:
            status = "fail"
            report["summary"]["failed"] += 1
            lemma = artifact.get("lexical_entry", {}).get("lemma", "unknown")
            print(f"[FAIL] {artifact.get('candidate_id', filename)} ({lemma})")
            for f in failures:
                print(f"       - {f['code']}: {f['message']}")
        elif flags:
            status = "flag"
            report["summary"]["flagged"] += 1
            lemma = artifact.get("lexical_entry", {}).get("lemma", "unknown")
            flag_codes = ", ".join(f["code"] for f in flags)
            print(f"[FLAG] {artifact.get('candidate_id', filename)} ({lemma}) — {flag_codes}")
        else:
            status = "pass"
            report["summary"]["passed"] += 1
            lemma = artifact.get("lexical_entry", {}).get("lemma", "unknown")
            print(f"[PASS] {artifact.get('candidate_id', filename)} ({lemma})")
            
        report["candidates"].append({
            "candidate_id": artifact.get("candidate_id", filename),
            "source_file": filename,
            "status": status,
            "checks": checks,
            "failures": failures,
            "flags": flags
        })
        
    report_path = os.path.join(val_dir, "report.json")
    write_json(report_path, report)
    
    print("\n--------------------------------")
    print(f"Total: {report['summary']['total']} | Passed: {report['summary']['passed']} | Flagged: {report['summary']['flagged']} | Failed: {report['summary']['failed']}")
    print(f"\nReport: {report_path}")
    
    if report["summary"]["failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m evaluation.artifact_validator <EXPERIMENT_ID>")
        sys.exit(2)
        
    main(sys.argv[1])
