import os
import json
import argparse

from evaluation.utils import (
    ROOT_DIR, EVAL_DIR, GOLDEN_SET_DIR, EXPERIMENTS_DIR, CONFIGS_DIR, PROMPTS_DIR, SCHEMAS_DIR,
    canonical_hash, get_file_hash, load_json, write_json
)

def _maybe_int(x):
    """Coerce to int when given a JSON integer or numeric string."""
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, str) and x.strip().lstrip('-').isdigit():
        return int(x)
    return x


# JSON-Schema-only metadata keys that are NOT valid Vertex `Schema` proto fields.
# The canonical schema file may carry these for schema-validation purposes, but the
# Vertex batch endpoint sends the on-disk JSONL verbatim to a `generateContentRequest`
# proto and rejects unknown fields. This is the transport-adapter seam: it isolates
# Google API constraints from the canonical semantic schema (see Architecture).
_SCHEMA_METADATA_KEYS = {"schema_version", "$schema"}


def _strip_schema_metadata(schema):
    """Return a copy of `schema` without JSON-Schema-only metadata keys.

    Transport adapter: maps the canonical JSON-Schema document onto the subset of
    fields the Vertex `Schema` proto understands. The canonical file is NOT mutated.
    """
    if not isinstance(schema, dict):
        return schema
    return {k: v for k, v in schema.items() if k not in _SCHEMA_METADATA_KEYS}


def build_batch_input(config_file, experiment_id):
    config_path = os.path.join(CONFIGS_DIR, config_file)
    if not os.path.exists(config_path):
        raise RuntimeError(f"Config file {config_path} not found.")

    config = load_json(config_path)

    # 1. Gate 8A.1: Golden Set Integrity (unchanged)
    golden_set_path = os.path.join(GOLDEN_SET_DIR, "golden_v2.json")
    manifest_path = os.path.join(GOLDEN_SET_DIR, "manifest.json")

    golden_manifest = load_json(manifest_path)
    actual_golden_hash = get_file_hash(golden_set_path)
    declared_hash = golden_manifest.get("golden_set_sha256")

    if actual_golden_hash != declared_hash:
        raise RuntimeError(f"Golden Set hash mismatch! Manifest: {declared_hash}, Actual: {actual_golden_hash}")

    golden_data = load_json(golden_set_path)

    # 8A.1b: Optional pilot subset — only run selected word IDs.
    # This keeps golden_v2 immutable as the baseline while the matrix uses a
    # fixed, smaller pilot set.
    pilot_manifest = None
    word_ids = config.get("word_ids")
    if word_ids:
        id_set = {_maybe_int(x) for x in word_ids}
        golden_data = [e for e in golden_data if _maybe_int(e.get('id')) in id_set]
        if len(golden_data) != len(id_set):
            missing = id_set - {_maybe_int(e.get('id')) for e in golden_data}
            raise RuntimeError(f"word_ids requested but {len(missing)} IDs not found in golden set: {sorted(missing)}")

        # Optional POS correction from a pilot manifest (documented data-error fixes).
        pilot_manifest_path = config.get("pilot_manifest")
        if pilot_manifest_path:
            pm_path = os.path.join(EVAL_DIR, pilot_manifest_path)
            pm = load_json(pm_path)
            pos_by_id = {_maybe_int(e["id"]): e.get("pos") for e in pm.get("entries", [])}
            for e in golden_data:
                corr = pos_by_id.get(_maybe_int(e.get("id")))
                if corr:
                    e["pos"] = corr

    # 2. Gate 8A.2: Prompt & Schema
    prompt_path = os.path.join(PROMPTS_DIR, f"{config['prompt_id']}.txt")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()

    schema_path = os.path.join(SCHEMAS_DIR, f"{config['schema_version']}.json")
    output_schema = _strip_schema_metadata(load_json(schema_path))

    # 3. Output Directory
    exp_dir = os.path.join(EXPERIMENTS_DIR, experiment_id)
    input_dir = os.path.join(exp_dir, "input")
    os.makedirs(input_dir, exist_ok=True)

    out_file = os.path.join(input_dir, "requests.jsonl")

    # 4. Generate JSONL Request Envelopes
    # Each line is { "key", "request" } where request is a GenerateContentRequest:
    #   contents (required), generationConfig (camelCase, Vertex REST), and
    #   optional top-level tools / systemInstruction.
    lines = []
    for i, entry in enumerate(golden_data):
        cand_id = f"{experiment_id}-CAND-{entry['id']}"

        prompt_text = prompt_template.format(
            lemma=entry['wordEn'],
            pos=entry['pos'],
            cefr=entry['cefrLevel'],
            id=entry['id']
        )

        gen_config = {
            "temperature": config.get('temperature', 0.2),
            "maxOutputTokens": config.get('max_output_tokens', 1024),
            "responseMimeType": "application/json",
            "responseSchema": output_schema
        }
        if config.get("top_p") is not None:
            gen_config["topP"] = config["top_p"]
        if config.get("top_k") is not None:
            gen_config["topK"] = config["top_k"]

        # --- ADDITIVE: thinking (Gemini 3) --------------------------------
        # thinking.level in {"low","medium","high"} (or "minimal" on flash-lite).
        # Emitted as generationConfig.thinkingConfig.thinkingLevel (Vertex camelCase).
        thinking = config.get("thinking", {}) or {}
        tlevel = thinking.get("level")
        if thinking.get("enabled", False) and tlevel:
            gen_config["thinkingConfig"] = {"thinkingLevel": tlevel}

        request = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt_text}]
                }
            ],
            "generationConfig": gen_config
        }

        # --- ADDITIVE: grounding with Google Search -----------------------
        # tools is a top-level field of GenerateContentRequest (parallel to
        # contents / generationConfig), per Vertex Grounding REST reference.
        grounding = config.get("grounding", {}) or {}
        if grounding.get("enabled") and grounding.get("google_search"):
            request["tools"] = [{"googleSearch": {}}]

        envelope = {
            "key": cand_id,
            "request": request
        }

        lines.append(json.dumps(envelope, ensure_ascii=False))

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines) + "\n")

    final_hash = get_file_hash(out_file)
    print(f"Generated exactly {len(lines)} requests in {out_file}")
    print(f"Input JSONL SHA-256: {final_hash}")
    return out_file, final_hash


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Config file name in evaluation/configs")
    parser.add_argument("--experiment-id", required=True, help="Experiment ID to use")
    args = parser.parse_args()
    build_batch_input(args.config, args.experiment_id)
