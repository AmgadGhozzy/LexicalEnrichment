import sqlite3
import json
import logging
import os
import sys
from llm_provider import VertexAIProvider

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.utils import load_file, sha256_string
from evaluation.lexical_validator import (
    VALID_REGISTERS,
    VALID_PRIMARY_SENSES,
    VALID_CATEGORIES,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Phase1")

STAGING_DB = os.path.join(ROOT_DIR, "data", "staging", "LexicalStaging.db")
SYSTEM_PROMPT_PATH = os.path.join(ROOT_DIR, "prompts", "system", "lexical_core.md")
TASK_PROMPT_PATH = os.path.join(ROOT_DIR, "prompts", "tasks", "lexical_core.md")
SCHEMA_PATH = os.path.join(ROOT_DIR, "config", "schemas", "lexical_core.json")

# Shared enum contract lives in evaluation.lexical_validator (single owner).
# Accepts a missing enum value as an ERROR (see validate_response).


def validate_response(enriched_words, expected_inputs):
    """Deterministic pre-write checks. Raises ValueError listing all issues."""
    errors = []
    
    expected_ids = list(expected_inputs.keys())

    # 1. Count match
    if len(enriched_words) != len(expected_ids):
        errors.append(
            f"Word count mismatch: sent {len(expected_ids)}, got {len(enriched_words)}"
        )

    # 2. Exact ID match
    actual_ids = {w.get("id") for w in enriched_words}
    if actual_ids != set(expected_ids):
        missing = set(expected_ids) - actual_ids
        extra = actual_ids - set(expected_ids)
        if missing:
            errors.append(f"Missing IDs in response: {missing}")
        if extra:
            errors.append(f"Unexpected extra IDs in response: {extra}")

    # 3. Per-word checks
    for w in enriched_words:
        w_id = w.get("id")
        label_word = f"Word {w_id}"
        
        # Identity parity check
        expected = expected_inputs.get(w_id)
        if expected:
            if w.get("lemma") != expected["lemma"]:
                errors.append(f"{label_word}: lemma mismatch (expected '{expected['lemma']}', got '{w.get('lemma')}')")
            if w.get("pos") != expected["pos"]:
                errors.append(f"{label_word}: POS mismatch (expected '{expected['pos']}', got '{w.get('pos')}')")
            if w.get("cefr_level") != expected["cefr_level"]:
                errors.append(f"{label_word}: CEFR mismatch (expected '{expected['cefr_level']}', got '{w.get('cefr_level')}')")

        # aiConfidence check
        conf = w.get("aiConfidence")
        if conf is None or not (0.0 <= float(conf) <= 1.0):
            errors.append(f"{label_word}: invalid or missing aiConfidence.")

        # Category check
        cat = w.get("category")
        if cat not in VALID_CATEGORIES:
            errors.append(f"{label_word}: invalid category '{cat}'.")

        # Translit check (must NOT exist in Phase 1)
        if "translit" in w:
            errors.append(f"{label_word}: 'translit' field is forbidden in Phase 1 output.")

        # Phonetics checks
        us = w.get("phonetic_us")
        if not us or not isinstance(us, str):
            errors.append(f"{label_word}: missing or invalid phonetic_us.")
        elif "/" in us:
            errors.append(f"{label_word}: phonetic_us '{us}' contains slashes '/'.")

        uk = w.get("phonetic_uk")
        if uk and "/" in uk:
            errors.append(f"{label_word}: phonetic_uk '{uk}' contains slashes '/'.")

        ar = w.get("phonetic_ar")
        if not ar or not isinstance(ar, str):
            errors.append(f"{label_word}: missing or invalid phonetic_ar.")

        senses = w.get("senses", [])
        if not senses:
            errors.append(f"{label_word}: no senses returned.")
            continue

        primary_count = sum(1 for s in senses if s.get("is_primary"))
        if primary_count != 1:
            errors.append(f"{label_word}: has {primary_count} primary senses (expected exactly 1).")

        for idx, s in enumerate(senses):
            label = f"{label_word} sense {idx + 1}"

            if "translit" in s:
                errors.append(f"{label}: 'translit' field is forbidden in Phase 1 sense.")

            if not s.get("sense_no"):
                errors.append(f"{label}: missing sense_no.")

            if not s.get("definition_en"):
                errors.append(f"{label}: missing definition_en.")

            if not s.get("definition_ar"):
                errors.append(f"{label}: missing definition_ar.")

            if not s.get("short_def_en"):
                errors.append(f"{label}: missing short_def_en.")

            if s.get("register") not in VALID_REGISTERS:
                errors.append(f"{label}: invalid register '{s.get('register')}'.")

            if s.get("primary_sense") not in VALID_PRIMARY_SENSES:
                errors.append(f"{label}: invalid primary_sense '{s.get('primary_sense')}'.")

            # Mnemonic format check
            mnem = s.get("mnemonic_ar")
            if mnem:
                if any(bracket in mnem for bracket in ["(", ")", "[", "]"]):
                    errors.append(f"{label}: mnemonic_ar contains forbidden brackets '()' or '[]'. Use double quotes \"\" only.")

            tags = s.get("semantic_tags")
            if not isinstance(tags, list):
                errors.append(f"{label}: semantic_tags is not an array.")
            else:
                if not (3 <= len(tags) <= 5):
                    errors.append(f"{label}: {len(tags)} tags, expected 3-5.")
                for t in tags:
                    if not str(t).startswith('#'):
                        errors.append(f"{label}: tag '{t}' does not start with '#'.")

    if errors:
        raise ValueError("Pre-write validation failed:\n  - " + "\n  - ".join(errors))


def run_phase1_test(limit=10):
    logger.info(f"Starting Phase 1: Lexical Core ({limit}-word smoke test)")

    try:
        provider = VertexAIProvider(model_name="gemini-2.5-flash")
    except Exception as e:
        logger.error(f"Failed to init LLM provider: {e}")
        return

    sys_prompt = load_file(SYSTEM_PROMPT_PATH)
    task_prompt_tmpl = load_file(TASK_PROMPT_PATH)
    schema_str = load_file(SCHEMA_PATH)
    schema = json.loads(schema_str)

    prompt_hash = sha256_string(sys_prompt + task_prompt_tmpl)
    schema_hash = sha256_string(schema_str)

    # --- Deterministic word selection: MIN(id) per lemma ---
    conn = sqlite3.connect(STAGING_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    test_lemmas = ['bank', 'right', 'record', 'present', 'object', 'get', 'set', 'take', 'lead', 'close']
    placeholders = ','.join(['?'] * len(test_lemmas))

    cursor.execute(f"""
        SELECT w.id, w.lemma, w.pos, w.cefr_level
        FROM words w
        INNER JOIN (
            SELECT lemma, MIN(id) AS min_id
            FROM words
            WHERE lemma IN ({placeholders})
            GROUP BY lemma
        ) sub ON w.id = sub.min_id
    """, test_lemmas)

    rows = cursor.fetchall()

    if len(rows) != len(test_lemmas):
        logger.warning(f"Expected {len(test_lemmas)} words, fetched {len(rows)}. Aborting.")
        return

    batch_input = [{"id": r["id"], "lemma": r["lemma"], "pos": r["pos"], "cefr_level": r["cefr_level"]} for r in rows]
    expected_inputs = {r["id"]: dict(r) for r in rows}

    logger.info(f"Batch: {[w['lemma'] for w in batch_input]}")

    batch_json_str = json.dumps(batch_input, ensure_ascii=False, indent=2)
    user_prompt = task_prompt_tmpl.replace("{{BATCH_JSON}}", batch_json_str)

    logger.info("Calling Vertex AI...")
    try:
        result = provider.generate_structured(sys_prompt, user_prompt, schema)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return

    enriched_words = result.get("words", [])

    # --- Pre-write validation (no DB touched yet) ---
    try:
        validate_response(enriched_words, expected_inputs)
    except ValueError as e:
        logger.error(str(e))
        scratch = os.path.join(ROOT_DIR, 'scratch')
        os.makedirs(scratch, exist_ok=True)
        with open(os.path.join(scratch, 'failed_smoke_test.json'), 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return

    # --- Create enrichment_run record (outside the batch transaction) ---
    cursor.execute("""
        INSERT INTO enrichment_runs (
            run_mode, stage, model, prompt_version, prompt_hash,
            schema_version, schema_hash, batch_size
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ('test', 'phase1_core', provider.model_name, 'v1.0', prompt_hash, 'v1.0', schema_hash, len(enriched_words)))
    run_id = cursor.lastrowid
    conn.commit()

    # --- Batch write transaction ---
    try:
        conn.execute("BEGIN TRANSACTION")

        for w_out in enriched_words:
            w_id = w_out.get("id")
            senses = w_out.get("senses", [])
            model_conf = w_out.get("aiConfidence")
            logger.info(f"  Writing word {w_id} ({len(senses)} senses)")

            cursor.execute("UPDATE words SET difficulty_score=?, category=? WHERE id=?",
                           (w_out.get("difficulty_score"), w_out.get("category"), w_id))

            cursor.execute("DELETE FROM pronunciations WHERE word_id=?", (w_id,))
            if w_out.get("phonetic_us"):
                cursor.execute("INSERT INTO pronunciations (word_id, variant, ipa) VALUES (?, 'us', ?)",
                               (w_id, w_out["phonetic_us"]))
            if w_out.get("phonetic_uk"):
                cursor.execute("INSERT INTO pronunciations (word_id, variant, ipa) VALUES (?, 'uk', ?)",
                               (w_id, w_out["phonetic_uk"]))
            if w_out.get("phonetic_ar"):
                cursor.execute("INSERT INTO pronunciations (word_id, variant, phonetic_ar) VALUES (?, 'ar', ?)",
                               (w_id, w_out["phonetic_ar"]))

            cursor.execute("DELETE FROM word_senses WHERE word_id=?", (w_id,))
            for sense in senses:
                cursor.execute("""
                    INSERT INTO word_senses (
                        word_id, sense_no, definition_en, definition_ar, short_def_en,
                        register, usage_note, mnemonic_ar, primary_sense, semantic_tags,
                        sense_status, source_evidence, is_primary, enrichment_run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated', 'Phase1_SmokeTest', ?, ?)
                """, (
                    w_id, sense.get("sense_no"), sense.get("definition_en"),
                    sense.get("definition_ar"), sense.get("short_def_en"),
                    sense.get("register"), sense.get("usage_note"),
                    sense.get("mnemonic_ar"), sense.get("primary_sense"),
                    json.dumps(sense.get("semantic_tags", []), ensure_ascii=False),
                    1 if sense.get("is_primary") else 0, run_id
                ))
                sense_id = cursor.lastrowid
                
                cursor.execute("""
                    INSERT INTO field_versions (
                        entity_type, entity_id, field_name, value,
                        pipeline_version, model, model_self_confidence, prompt_hash, status
                    ) VALUES ('sense', ?, 'lexical_core_bundle', ?, 'v2.0_phase1', ?, ?, ?, 'current')
                """, (sense_id, json.dumps(sense, ensure_ascii=False), provider.model_name, model_conf, prompt_hash))

        conn.commit()

        # Mark run complete (separate commit, safe even if the above fails mid-way)
        cursor.execute("UPDATE enrichment_runs SET status='completed', words_processed=?, words_passed=? WHERE id=?",
                       (len(enriched_words), len(enriched_words), run_id))
        conn.commit()

        logger.info("Smoke test complete. Results saved to scratch/smoke_test_results.json")
        scratch = os.path.join(ROOT_DIR, 'scratch')
        os.makedirs(scratch, exist_ok=True)
        with open(os.path.join(scratch, 'smoke_test_results.json'), 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    except Exception as e:
        conn.rollback()
        logger.error(f"Batch write failed. Rollback executed. Error: {e}")

        # Mark run failed in its own auto-commit statement
        try:
            cursor.execute("UPDATE enrichment_runs SET status='failed' WHERE id=?", (run_id,))
            conn.commit()
        except Exception as inner:
            logger.error(f"Could not mark run as failed: {inner}")


if __name__ == "__main__":
    run_phase1_test(10)
