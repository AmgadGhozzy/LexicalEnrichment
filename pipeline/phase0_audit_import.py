import sqlite3
import json
import hashlib
import os
import sys
import logging
from datetime import datetime

# Ensure the project root is importable regardless of how this module is invoked.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.utils import hash_file_bytes

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Phase0")

# Paths
SOURCE_DB = r"C:\Users\HP\Desktop\DictionaryEnrichment\LexicalEngine\WordsMaster.db"
STAGING_DB = os.path.join(ROOT_DIR, "data", "staging", "LexicalStaging.db")
SCHEMA_PATH = os.path.join(ROOT_DIR, "db", "schema.sql")

def init_staging_db():
    """Create the staging database and apply the schema."""
    logger.info(f"Initializing staging DB at {STAGING_DB}")
    if os.path.exists(STAGING_DB):
        logger.warning(f"Staging DB already exists. Deleting it for a fresh import.")
        os.remove(STAGING_DB)
    
    conn = sqlite3.connect(STAGING_DB)
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    cursor = conn.cursor()
    cursor.executescript(schema_sql)
    conn.commit()
    conn.close()
    logger.info("Schema applied successfully.")

def run_import():
    """Read from source DB and import to staging DB."""
    if not os.path.exists(SOURCE_DB):
        logger.error(f"Source DB not found at {SOURCE_DB}")
        sys.exit(1)

    source_hash = hash_file_bytes(SOURCE_DB)
    logger.info(f"Source DB SHA-256: {source_hash}")

    # Connect to both DBs
    source_conn = sqlite3.connect(SOURCE_DB)
    source_conn.row_factory = sqlite3.Row
    staging_conn = sqlite3.connect(STAGING_DB)

    source_cursor = source_conn.cursor()
    staging_cursor = staging_conn.cursor()

    source_cursor.execute("SELECT * FROM wordsMaster")
    rows = source_cursor.fetchall()
    
    logger.info(f"Found {len(rows)} records in source DB. Starting import...")

    staging_conn.execute("BEGIN TRANSACTION")
    
    imported_count = 0
    error_count = 0

    for row in rows:
        d = dict(row)
        
        try:
            # 1. Normalize core data
            lemma = d.get('wordEn', '').strip()
            if not lemma:
                continue
                
            normalized_lemma = lemma.lower()
            
            pos = d.get('pos', '').strip()
            if not pos:
                logger.error(f"Missing POS for word ID {d.get('id', 'Unknown')}. Failing import.")
                error_count += 1
                continue
                
            cefr = d.get('cefrLevel', '').strip()
            if cefr not in ['A1','A2','B1','B2','C1','C2']:
                logger.error(f"Invalid CEFR '{cefr}' for word ID {d.get('id', 'Unknown')}. Failing import.")
                error_count += 1
                continue
                
            frequency = float(d.get('frequency', 0.0) or 0.0)
            rank = int(d.get('rank', 0) or 0)
            oxford_flag = int(d.get('fromOxford', 0) or 0)
            category = d.get('category')
            difficulty = str(d.get('difficultyScore', '')) if d.get('difficultyScore') else None
            syllabify = d.get('syllabify')

            # 2. Insert into `words` table
            staging_cursor.execute("""
                INSERT INTO words (
                    id, lemma, normalized_lemma, pos, cefr_level, 
                    frequency, frequency_rank, difficulty_score, 
                    oxford_flag, category, syllabify
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                d['id'], lemma, normalized_lemma, pos, cefr,
                frequency, rank, difficulty, oxford_flag, category, syllabify
            ))

            # 3. Create Source Record (Immutable lineage)
            raw_json = json.dumps(d, ensure_ascii=False)
            row_hash = hashlib.sha256(raw_json.encode('utf-8')).hexdigest()

            staging_cursor.execute("""
                INSERT INTO source_records (
                    source_db, source_table, source_row_id, raw_json, source_hash
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                "WordsMaster.db", "wordsMaster", d['id'], raw_json, row_hash
            ))

            imported_count += 1
            
        except Exception as e:
            logger.error(f"Error importing row {d.get('id')}: {e}")
            error_count += 1

    staging_conn.commit()
    
    # Run a quick audit on the staging DB
    staging_cursor.execute("SELECT COUNT(*) FROM words")
    final_count = staging_cursor.fetchone()[0]
    
    logger.info(f"Import complete.")
    logger.info(f"  Attempted: {len(rows)}")
    logger.info(f"  Imported:  {imported_count}")
    logger.info(f"  Failed:    {error_count}")
    logger.info(f"  Staging words count: {final_count}")

    source_conn.close()
    staging_conn.close()

if __name__ == "__main__":
    logger.info("=== Phase 0: Audit & Import ===")
    init_staging_db()
    run_import()
