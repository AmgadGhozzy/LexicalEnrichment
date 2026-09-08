import sqlite3
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.lexical_validator import (
    VALID_REGISTERS,
    VALID_PRIMARY_SENSES,
    VALID_CATEGORIES,
)

STAGING_DB = os.path.join(ROOT_DIR, "data", "staging", "LexicalStaging.db")

# Shared enum contract lives in evaluation.lexical_validator (single owner).
# verify_staging_integrity is a DB AUDIT: it CONSUMES the contract but is
# itself out of LexicalValidator's scope (which never touches SQLite).

def verify_staging_integrity(run_id=None):
    if not os.path.exists(STAGING_DB):
        print(f"ERROR: Database file {STAGING_DB} does not exist.")
        return False

    conn = sqlite3.connect(STAGING_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 70)
    print("LEXICAL STAGING INTEGRITY VERIFICATION (POST-RUN AUDIT)")
    print("=" * 70)

    # 1. Check enrichment_runs
    if run_id:
        cursor.execute("SELECT * FROM enrichment_runs WHERE id = ?", (run_id,))
    else:
        cursor.execute("SELECT * FROM enrichment_runs ORDER BY id DESC LIMIT 1")
    
    run = cursor.fetchone()
    if not run:
        print("[-] No enrichment runs found in database.")
        return False

    run_id = run["id"]
    print(f"[*] Audit target Run ID: {run_id}")
    print(f"    - Stage: {run['stage']}")
    print(f"    - Model: {run['model']}")
    print(f"    - Status: {run['status']}")
    print(f"    - Processed: {run['words_processed']}, Passed: {run['words_passed']}, Failed: {run['words_failed']}")

    checks_passed = True
    issues = []

    if run["status"] != "completed":
        issues.append(f"Run {run_id} status is '{run['status']}', expected 'completed'.")
        checks_passed = False

    # 2. Get senses associated with this run
    cursor.execute("""
        SELECT ws.*, w.lemma, w.pos, w.category, w.difficulty_score
        FROM word_senses ws
        JOIN words w ON ws.word_id = w.id
        WHERE ws.enrichment_run_id = ?
        ORDER BY ws.word_id, ws.sense_no
    """, (run_id,))
    senses = cursor.fetchall()

    if not senses:
        issues.append(f"No word senses found associated with Run ID {run_id}.")
        checks_passed = False
        print(f"[-] {issues[-1]}")
        return False

    # Group senses by word_id
    words_senses_map = {}
    for s in senses:
        w_id = s["word_id"]
        words_senses_map.setdefault(w_id, []).append(s)

    print(f"[*] Enriched words count in Run: {len(words_senses_map)} words, {len(senses)} total senses.")

    # 3. Detailed per-word and per-sense checks
    for w_id, w_senses in words_senses_map.items():
        first_s = w_senses[0]
        lemma = first_s["lemma"]
        pos = first_s["pos"]
        category = first_s["category"]
        diff = first_s["difficulty_score"]

        # Word-level checks
        if category not in VALID_CATEGORIES:
            issues.append(f"Word {lemma} (ID {w_id}): invalid category '{category}'")
            checks_passed = False

        # Pronunciations check
        cursor.execute("SELECT * FROM pronunciations WHERE word_id = ?", (w_id,))
        prons = {p["variant"]: p for p in cursor.fetchall()}

        if "us" not in prons or not prons["us"]["ipa"]:
            issues.append(f"Word {lemma} (ID {w_id}): missing US IPA pronunciation")
            checks_passed = False
        elif "/" in (prons["us"]["ipa"] or ""):
            issues.append(f"Word {lemma} (ID {w_id}): US IPA '{prons['us']['ipa']}' contains slashes")
            checks_passed = False

        if "uk" in prons and prons["uk"]["ipa"] and "/" in prons["uk"]["ipa"]:
            issues.append(f"Word {lemma} (ID {w_id}): UK IPA '{prons['uk']['ipa']}' contains slashes")
            checks_passed = False

        if "ar" not in prons or not prons["ar"]["phonetic_ar"]:
            issues.append(f"Word {lemma} (ID {w_id}): missing Arabic phonetics (phonetic_ar)")
            checks_passed = False

        # Sense-level checks
        primary_senses = [s for s in w_senses if s["is_primary"] == 1]
        if len(primary_senses) != 1:
            issues.append(f"Word {lemma} (ID {w_id}): has {len(primary_senses)} primary senses (expected exactly 1)")
            checks_passed = False

        for s in w_senses:
            s_id = s["id"]
            s_label = f"Word {lemma} (ID {w_id}) Sense #{s['sense_no']}"

            if not s["definition_en"] or not s["definition_ar"] or not s["short_def_en"]:
                issues.append(f"{s_label}: missing one or more definitions (en, ar, short_en)")
                checks_passed = False

            if s["register"] not in VALID_REGISTERS:
                issues.append(f"{s_label}: invalid register '{s['register']}'")
                checks_passed = False

            if s["primary_sense"] not in VALID_PRIMARY_SENSES:
                issues.append(f"{s_label}: invalid primary_sense '{s['primary_sense']}'")
                checks_passed = False

            mnem = s["mnemonic_ar"]
            if mnem and any(b in mnem for b in ["(", ")", "[", "]"]):
                issues.append(f"{s_label}: mnemonic_ar contains brackets: '{mnem}'")
                checks_passed = False

            # Semantic tags check
            try:
                tags = json.loads(s["semantic_tags"] or "[]")
                if not isinstance(tags, list) or not (3 <= len(tags) <= 5):
                    issues.append(f"{s_label}: semantic_tags count is {len(tags)}, expected 3-5")
                    checks_passed = False
                for t in tags:
                    if not str(t).startswith("#"):
                        issues.append(f"{s_label}: tag '{t}' does not start with '#'")
                        checks_passed = False
            except Exception as e:
                issues.append(f"{s_label}: semantic_tags JSON error: {e}")
                checks_passed = False

            # Field versions audit record check
            cursor.execute("""
                SELECT COUNT(*) FROM field_versions
                WHERE entity_type = 'sense' AND entity_id = ?
            """, (s_id,))
            fv_count = cursor.fetchone()[0]
            if fv_count == 0:
                issues.append(f"{s_label}: missing field_versions audit record")
                checks_passed = False

    # 4. Parity check with scratch/smoke_test_results.json (if exists)
    json_path = os.path.join(ROOT_DIR, "scratch", "smoke_test_results.json")
    if os.path.exists(json_path):
        print("[*] Performing Parity Check: scratch/smoke_test_results.json <-> SQLite DB...")
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            json_words = json_data.get("words", [])
            
            if len(json_words) != len(words_senses_map):
                issues.append(f"Parity mismatch: JSON has {len(json_words)} words, DB has {len(words_senses_map)}")
                checks_passed = False
            
            for jw in json_words:
                jw_id = jw.get("id")
                if jw_id not in words_senses_map:
                    issues.append(f"Parity mismatch: Word ID {jw_id} in JSON but not in DB senses.")
                    checks_passed = False
                    continue
                
                db_senses = words_senses_map[jw_id]
                jw_senses = jw.get("senses", [])
                if len(db_senses) != len(jw_senses):
                    issues.append(f"Parity mismatch Word ID {jw_id}: JSON has {len(jw_senses)} senses, DB has {len(db_senses)}")
                    checks_passed = False
        except Exception as e:
            issues.append(f"Parity check error reading JSON: {e}")
            checks_passed = False

    print("-" * 70)
    if checks_passed and not issues:
        print("[+] ALL INTEGRITY, CONTRACT, AND JSON<->SQLITE PARITY CHECKS PASSED!")
        print(f"[+] Total Words Verified: {len(words_senses_map)}")
        print(f"[+] Total Senses Verified: {len(senses)}")
        print("-" * 70)
        # Print a sample table
        print(f"{'ID':<6}{'Lemma':<12}{'POS':<8}{'Category':<22}{'Senses':<8}{'Primary Sense':<16}")
        print("-" * 70)
        for w_id, w_senses in words_senses_map.items():
            first_s = w_senses[0]
            pri_s = next((s for s in w_senses if s["is_primary"] == 1), w_senses[0])
            print(f"{w_id:<6}{first_s['lemma']:<12}{first_s['pos']:<8}{str(first_s['category'])[:20]:<22}{len(w_senses):<8}{pri_s['primary_sense']:<16}")
        print("=" * 70)
        return True
    else:
        print(f"[-] INTEGRITY CHECK FAILED with {len(issues)} issue(s):")
        for iss in issues:
            print(f"    - {iss}")
        print("=" * 70)
        return False

if __name__ == "__main__":
    target_run = int(sys.argv[1]) if len(sys.argv) > 1 else None
    verify_staging_integrity(target_run)
