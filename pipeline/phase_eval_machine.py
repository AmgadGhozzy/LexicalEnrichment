import sqlite3
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PhaseEvalMachine")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.lexical_validator import VALID_REGISTERS, VALID_PRIMARY_SENSES

STAGING_DB = os.path.join(ROOT_DIR, "data", "staging", "LexicalStaging.db")
BASELINE_PATH = os.path.join(ROOT_DIR, "data", "evaluation", "legacy_baseline_200.json")

# Shared enum contract lives in evaluation.lexical_validator (single owner).
# evaluate_word's acceptance semantics are LAZY: a missing enum is tolerated;
# only an invalid SUPPLIED value is an ERROR. Keep this distinct from the
# phase1/verify sites where a missing enum is an ERROR.

def load_baseline():
    with open(BASELINE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Map by word_id
    return {w['word_id']: w for w in data}

def evaluate_word(eval_id, word_id, raw_payload, legacy_data):
    try:
        v2 = json.loads(raw_payload)
    except Exception as e:
        return {
            "machine_validation_result": "json_parse_failed",
            "decision": "manual_review",
            "reason": f"JSON parse error: {e}"
        }

    legacy = legacy_data['legacy']
    
    # Validation checks
    if not isinstance(v2, dict):
        return {"machine_validation_result": "schema_failed", "decision": "manual_review", "reason": "Root is not object"}
        
    expected_lemma = legacy.get('wordEn')
    expected_pos = legacy.get('pos')
    
    if v2.get('lemma') != expected_lemma:
        return {"machine_validation_result": "wrong_word", "decision": "manual_review", "reason": f"Expected {expected_lemma}, got {v2.get('lemma')}"}
        
    if v2.get('pos') != expected_pos:
        return {"machine_validation_result": "wrong_pos", "decision": "manual_review", "reason": f"Expected {expected_pos}, got {v2.get('pos')}"}
        
    if 'senses' not in v2 or not isinstance(v2['senses'], list) or len(v2['senses']) == 0:
        return {"machine_validation_result": "missing_required", "decision": "manual_review", "reason": "Missing or empty senses array"}

    for s in v2['senses']:
        if s.get('register') and s.get('register') not in VALID_REGISTERS:
            return {"machine_validation_result": "invalid_enum", "decision": "manual_review", "reason": f"Invalid register {s.get('register')}"}
        if s.get('primary_sense') and s.get('primary_sense') not in VALID_PRIMARY_SENSES:
            return {"machine_validation_result": "invalid_enum", "decision": "manual_review", "reason": f"Invalid primary_sense {s.get('primary_sense')}"}

    # If it passes contract
    machine_validation_result = "pass"
    
    # 1. Structural Score (Are the required keys present?)
    req_keys = ['lemma', 'pos', 'phonetic_us', 'phonetic_ar', 'senses']
    struct_score = sum(1 for k in req_keys if k in v2) / len(req_keys)
    
    # 2. Content Completeness (Are the fields actually populated with meaningful data?)
    content_points = 0
    total_content_checks = 4
    if v2.get('phonetic_us') and len(v2['phonetic_us']) > 0: content_points += 1
    if v2.get('phonetic_ar') and len(v2['phonetic_ar']) > 0: content_points += 1
    
    valid_senses = 0
    for s in v2['senses']:
        if s.get('definition_en') and len(s['definition_en']) > 5:
            valid_senses += 1
    if valid_senses > 0: content_points += 1
    if valid_senses == len(v2['senses']): content_points += 1
    
    content_score = content_points / total_content_checks
    
    # 3. Preservation Score, Loss Score & Field Comparison
    # preservation_score = % of Legacy good data that V2 kept (0.0–1.0)
    # loss_score         = 1.0 if ANY field was removed (binary penalty flag)
    #                      0.0 = no loss
    fc = {"fields": {}, "additions": [], "removals": []}
    
    preservation_points = 0
    total_preservation = 0
    removals = []
    additions = []
    
    # --- Mnemonic ---
    leg_mnem = legacy.get('mnemonicAr')
    has_leg_mnem = bool(leg_mnem and str(leg_mnem).strip())
    v2_mnem = any(s.get('mnemonic_ar') for s in v2['senses'])
    
    if has_leg_mnem:
        total_preservation += 1
        if v2_mnem:
            preservation_points += 1
            fc['fields']['mnemonic'] = {"legacy": "present", "v2": "present", "status": "preserved"}
        else:
            fc['fields']['mnemonic'] = {"legacy": "present", "v2": "missing", "status": "removed"}
            removals.append("mnemonic_ar")
    else:
        if v2_mnem:
            fc['fields']['mnemonic'] = {"legacy": "missing", "v2": "present", "status": "added"}
            additions.append("mnemonic_ar")
        else:
            fc['fields']['mnemonic'] = {"legacy": "missing", "v2": "missing", "status": "unchanged"}
            
    # --- UK IPA ---
    leg_uk = legacy.get('phoneticUk')
    has_leg_uk = bool(leg_uk and str(leg_uk).strip())
    
    # User clarification: If V2 UK IPA is empty, it implies it is identical to V2 US IPA.
    # Therefore, it is not "missing", it is just implicitly the same.
    v2_uk_raw = v2.get('phonetic_uk')
    if not v2_uk_raw or not str(v2_uk_raw).strip():
        v2_uk_val = v2.get('phonetic_us')
    else:
        v2_uk_val = v2_uk_raw
        
    v2_uk = bool(v2_uk_val and str(v2_uk_val).strip())
    
    if has_leg_uk:
        total_preservation += 1
        if v2_uk:
            preservation_points += 1
            fc['fields']['phonetic_uk'] = {"legacy": str(leg_uk), "v2": str(v2_uk_val), "status": "preserved"}
        else:
            fc['fields']['phonetic_uk'] = {"legacy": str(leg_uk), "v2": None, "status": "removed"}
            removals.append("phonetic_uk")
    else:
        if v2_uk:
            fc['fields']['phonetic_uk'] = {"legacy": None, "v2": str(v2_uk_val), "status": "added"}
            additions.append("phonetic_uk")
        else:
            fc['fields']['phonetic_uk'] = {"legacy": None, "v2": None, "status": "unchanged"}
    
    # --- Senses added ---
    legacy_sense_count = 1  # Legacy is always single-sense flat
    v2_sense_count = len(v2.get('senses', []))
    if v2_sense_count > legacy_sense_count:
        additions.append(f"senses +{v2_sense_count - legacy_sense_count}")
    fc['fields']['senses'] = {
        "legacy": legacy_sense_count,
        "v2": v2_sense_count,
        "status": "expanded" if v2_sense_count > legacy_sense_count else "unchanged"
    }
    
    # --- Phase 1 does not generate these — not_evaluated ---
    fc['fields']['examples'] = {"legacy": "present", "v2": None, "status": "not_evaluated"}
    fc['fields']['collocations'] = {"legacy": "present", "v2": None, "status": "not_evaluated"}
    
    fc['additions'] = additions
    fc['removals'] = removals
    
    preservation_score = (preservation_points / total_preservation) if total_preservation > 0 else 1.0
    loss_score = 1.0 if removals else 0.0  # 1.0 = loss detected, 0.0 = no loss
    
    return {
        "machine_validation_result": machine_validation_result,
        "structural_score": struct_score,
        "content_completeness": content_score,
        "preservation_score": preservation_score,
        "loss_score": loss_score,
        "field_comparison": json.dumps(fc, ensure_ascii=False)
    }

def main():
    logger.info("Starting Machine Evaluation...")
    baseline = load_baseline()
    
    conn = sqlite3.connect(STAGING_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT id, word_id, raw_generated_payload FROM word_evaluations WHERE machine_validation_result IS NULL")
    rows = c.fetchall()
    
    logger.info(f"Found {len(rows)} evaluations to process.")
    
    # We need to map LexicalStaging words.id back to WordsMaster id to get the legacy baseline.
    c.execute("SELECT id, source_row_id FROM source_records WHERE source_db='WordsMaster.db'")
    staging_to_legacy = {r['id']: r['source_row_id'] for r in c.fetchall()}
    
    updates = []
    
    for r in rows:
        eval_id = r['id']
        staging_id = r['word_id']
        raw = r['raw_generated_payload']
        
        legacy_id = staging_to_legacy.get(staging_id)
        if not legacy_id or legacy_id not in baseline:
            logger.error(f"Cannot find baseline for staging_id {staging_id}")
            continue
            
        legacy_data = baseline[legacy_id]
        
        res = evaluate_word(eval_id, staging_id, raw, legacy_data)
        
        if res.get('machine_validation_result') != 'pass':
            updates.append((
                res['machine_validation_result'],
                None, None, None, None, None,
                res['decision'],
                res['reason'],
                eval_id
            ))
        else:
            updates.append((
                res['machine_validation_result'],
                res['structural_score'],
                res['content_completeness'],
                res['preservation_score'],
                res['loss_score'],
                res['field_comparison'],
                None, # decision
                None, # reason
                eval_id
            ))
            
    conn.execute("BEGIN TRANSACTION")
    c.executemany("""
        UPDATE word_evaluations SET 
            machine_validation_result=?,
            structural_score=?,
            content_completeness=?,
            preservation_score=?,
            loss_score=?,
            field_comparison=?,
            decision=?,
            reason=?
        WHERE id=?
    """, updates)
    conn.commit()
    
    logger.info(f"Successfully processed and updated {len(updates)} records.")

if __name__ == "__main__":
    main()
