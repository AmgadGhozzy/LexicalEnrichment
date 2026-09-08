import sqlite3
import json
import logging
import os
import sys
import time
import argparse
from datetime import datetime
from llm_provider import VertexAIProvider

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.utils import load_file, sha256_string

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PhaseEvalRunner")

STAGING_DB = os.path.join(ROOT_DIR, "data", "staging", "LexicalStaging.db")
BASELINE_PATH = os.path.join(ROOT_DIR, "data", "evaluation", "legacy_baseline_200.json")
SYSTEM_PROMPT_PATH = os.path.join(ROOT_DIR, "prompts", "system", "lexical_core.md")
TASK_PROMPT_PATH = os.path.join(ROOT_DIR, "prompts", "tasks", "lexical_core.md")
SCHEMA_PATH = os.path.join(ROOT_DIR, "config", "schemas", "lexical_core.json")

def get_word_id_mapping(conn):
    """Get mapping from WordsMaster.db ID to LexicalStaging.db words.id"""
    c = conn.cursor()
    c.execute("SELECT id, source_row_id FROM source_records WHERE source_db='WordsMaster.db' AND source_table='wordsMaster'")
    return {r['source_row_id']: r['id'] for r in c.fetchall()}

def main():
    parser = argparse.ArgumentParser(description="Run Phase 1 LLM Generation in Isolated Evaluation Mode")
    parser.add_argument('--dry-run', action='store_true', help="Do everything except call LLM and write DB")
    parser.add_argument('--test-limit', type=int, default=0, help="Limit to N words for testing (0 = all)")
    args = parser.parse_args()

    if not os.path.exists(BASELINE_PATH):
        logger.error(f"Baseline file missing: {BASELINE_PATH}")
        return

    with open(BASELINE_PATH, 'r', encoding='utf-8') as f:
        baseline_data = json.load(f)

    # Reorder baseline so that test words are first
    test_lemmas = {'bank', 'record', 'set', 'close', 'lead'}
    test_words = [w for w in baseline_data if w['word_en'].lower() in test_lemmas]
    other_words = [w for w in baseline_data if w['word_en'].lower() not in test_lemmas]
    baseline_data = test_words + other_words

    if args.test_limit > 0:
        baseline_data = baseline_data[:args.test_limit]
        logger.info(f"Limiting to {args.test_limit} words for testing.")

    logger.info(f"Loaded {len(baseline_data)} words from baseline.")

    sys_prompt = load_file(SYSTEM_PROMPT_PATH)
    task_prompt_tmpl = load_file(TASK_PROMPT_PATH)
    schema_str = load_file(SCHEMA_PATH)
    schema = json.loads(schema_str)

    prompt_hash = sha256_string(sys_prompt + task_prompt_tmpl)
    schema_hash = sha256_string(schema_str)
    
    conn = sqlite3.connect(STAGING_DB)
    conn.row_factory = sqlite3.Row
    id_mapping = get_word_id_mapping(conn)

    model_name = "gemini-2.5-flash"
    pipeline_version = "v1.0-eval-isolated"
    temperature = 0.0  # structured generation

    if args.dry_run:
        logger.info("DRY RUN: Would create evaluation_run and process words.")
        for b in baseline_data:
            staging_id = id_mapping.get(b['word_id'])
            logger.info(f"  Dry-run check: Legacy ID {b['word_id']} -> Staging ID {staging_id} ({b['word_en']})")
        return

    try:
        provider = VertexAIProvider(model_name=model_name)
    except Exception as e:
        logger.error(f"Failed to init LLM provider: {e}")
        return

    # Create run
    c = conn.cursor()
    c.execute("""
        INSERT INTO evaluation_runs (
            sample_size, model, prompt_hash, schema_hash, evaluator_version, status
        ) VALUES (?, ?, ?, ?, ?, 'running')
    """, (len(baseline_data), model_name, prompt_hash, schema_hash, pipeline_version))
    run_id = c.lastrowid
    conn.commit()
    logger.info(f"Created evaluation_run {run_id}")

    batch_size = 10
    total_processed = 0

    for i in range(0, len(baseline_data), batch_size):
        batch = baseline_data[i:i+batch_size]
        batch_id = f"run_{run_id}_batch_{i//batch_size}"
        logger.info(f"Processing batch {batch_id} ({len(batch)} words)")

        batch_input = []
        for b in batch:
            staging_id = id_mapping.get(b['word_id'])
            if not staging_id:
                logger.error(f"Could not map Legacy ID {b['word_id']} to Staging ID!")
                continue
            batch_input.append({
                "id": staging_id,
                "lemma": b['word_en'],
                "pos": b['pos'],
                "cefr_level": b['legacy']['cefrLevel']
            })

        batch_json_str = json.dumps(batch_input, ensure_ascii=False, indent=2)
        user_prompt = task_prompt_tmpl.replace("{{BATCH_JSON}}", batch_json_str)

        started_at = datetime.utcnow().isoformat() + "Z"
        start_time = time.time()
        
        try:
            result = provider.generate_structured(sys_prompt, user_prompt, schema)
        except Exception as e:
            logger.error(f"LLM call failed for batch: {e}")
            continue
            
        completed_at = datetime.utcnow().isoformat() + "Z"
        latency_ms = int((time.time() - start_time) * 1000)

        # Note: input_tokens and output_tokens might not be available from provider wrapper yet, default to 0
        input_tokens = result.get('usage', {}).get('input_tokens', 0)
        output_tokens = result.get('usage', {}).get('output_tokens', 0)

        enriched_words = result.get("words", [])
        
        # Save to DB
        conn.execute("BEGIN TRANSACTION")
        try:
            for w_out in enriched_words:
                w_id = w_out.get("id")
                raw_payload = json.dumps(w_out, ensure_ascii=False)
                
                c.execute("""
                    INSERT INTO word_evaluations (
                        run_id, word_id, raw_generated_payload,
                        model, prompt_hash, schema_hash, pipeline_version,
                        temperature, batch_id, request_index,
                        started_at, completed_at, latency_ms,
                        input_tokens, output_tokens, evaluator_version
                    ) VALUES (
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?
                    )
                """, (
                    run_id, w_id, raw_payload,
                    model_name, prompt_hash, schema_hash, pipeline_version,
                    temperature, batch_id, i//batch_size,
                    started_at, completed_at, latency_ms,
                    input_tokens, output_tokens, pipeline_version
                ))
            conn.commit()
            total_processed += len(enriched_words)
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save DB batch: {e}")

    c.execute("UPDATE evaluation_runs SET status='completed' WHERE id=?", (run_id,))
    conn.commit()
    logger.info(f"Evaluation run {run_id} completed. Processed {total_processed} words.")

if __name__ == "__main__":
    main()
