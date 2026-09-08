import sqlite3
import os
import hashlib
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Preflight")

SOURCE_DB = r"C:\Users\HP\Desktop\DictionaryEnrichment\LexicalEngine\WordsMaster.db"

def run_preflight():
    logger.info("=== PREFLIGHT CHECK ===")
    
    if not os.path.exists(SOURCE_DB):
        logger.error(f"CRITICAL: Source DB not found at {SOURCE_DB}")
        return False
        
    file_size_mb = os.path.getsize(SOURCE_DB) / (1024 * 1024)
    logger.info(f"File exists. Size: {file_size_mb:.2f} MB")
    
    # Calculate Hash
    sha256 = hashlib.sha256()
    with open(SOURCE_DB, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    file_hash = sha256.hexdigest()
    logger.info(f"SHA-256: {file_hash}")
    
    # Check database integrity and content
    try:
        conn = sqlite3.connect(SOURCE_DB)
        cursor = conn.cursor()
        
        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Tables found: {tables}")
        
        if 'wordsMaster' not in tables:
            logger.error("CRITICAL: 'wordsMaster' table not found in source DB.")
            return False
            
        # Get columns
        cursor.execute("PRAGMA table_info(wordsMaster)")
        columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Columns in wordsMaster: {len(columns)} columns")
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM wordsMaster")
        row_count = cursor.fetchone()[0]
        logger.info(f"Total Words (rows): {row_count}")
        
        if row_count == 0:
            logger.error("CRITICAL: Source DB is empty.")
            return False
            
        conn.close()
        
        logger.info("=== PREFLIGHT PASSED ===")
        print(f"\nAll checks passed. {row_count} words ready for Phase 0 processing.")
        print(f"Hash: {file_hash}")
        return True
        
    except Exception as e:
        logger.error(f"CRITICAL: Failed to read source DB: {e}")
        return False

if __name__ == "__main__":
    run_preflight()
