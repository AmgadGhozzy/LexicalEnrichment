import sqlite3
import json
import re
import logging
from typing import List, Dict

# -------------------------------------------------
# LOGGING
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("DataSanitizer")

# -------------------------------------------------
# CONSTANTS
# -------------------------------------------------
MAX_DEFINITIONS = 3
MAX_SYNONYMS = 5
MAX_ANTONYMS = 3
MAX_COLLOCATIONS = 5
MAX_RELATED = 6
MAX_EXAMPLES = 6

ARABIC_RE = re.compile(r'[\u0600-\u06FF]')

CEFR_BUCKETS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# -------------------------------------------------
# UTILITIES
# -------------------------------------------------
def is_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text or ""))


def safe_json_load(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def split_star(text: str) -> List[str]:
    return [normalize_text(p) for p in text.split("☆") if len(p.strip()) > 4]


# -------------------------------------------------
# CLEANERS
# -------------------------------------------------
def clean_definitions(raw: str) -> List[str]:
    if not raw:
        return []
    parts = split_star(raw)
    unique = []
    for p in parts:
        if p.lower() not in [x.lower() for x in unique]:
            unique.append(p)
    return unique[:MAX_DEFINITIONS]


def clean_list_field(raw, max_items) -> List[str]:
    if not raw:
        return []
    data = safe_json_load(raw)
    if isinstance(data, list):
        items = data
    else:
        items = re.split(r"[☆;,]", str(raw))

    clean = []
    for i in items:
        t = normalize_text(str(i))
        if len(t) > 2 and t.lower() not in [x.lower() for x in clean]:
            clean.append(t)
    return clean[:max_items]


def balance_related_words(raw) -> Dict[str, List[str]]:
    en, ar = [], []

    data = safe_json_load(raw)
    combined = []

    if isinstance(data, dict):
        combined += data.get("en", [])
        combined += data.get("ar", [])
    else:
        combined += clean_list_field(raw, MAX_RELATED * 2)

    for item in combined:
        if is_arabic(item):
            if item not in ar:
                ar.append(item)
        else:
            lw = item.lower()
            if lw not in en:
                en.append(lw)

    return {
        "en": en[:MAX_RELATED],
        "ar": ar[:MAX_RELATED]
    }


def clean_word_family(raw):
    """
    WordFamily is trusted ONLY if it's structurally valid.
    Otherwise: null seed for Gemini.
    """
    data = safe_json_load(raw)
    if not isinstance(data, dict):
        return None

    if all(not v for v in data.values()):
        return None

    # Very weak heuristic: same root letters
    return None


def classify_examples(raw_examples: List[str]) -> Dict[str, List[str]]:
    """
    Classify by sentence length (proxy for CEFR)
    """
    buckets = {k: [] for k in CEFR_BUCKETS}

    for ex in raw_examples:
        wc = len(ex.split())
        if wc <= 6:
            buckets["A1"].append(ex)
        elif wc <= 9:
            buckets["A2"].append(ex)
        elif wc <= 13:
            buckets["B1"].append(ex)
        elif wc <= 18:
            buckets["B2"].append(ex)
        elif wc <= 24:
            buckets["C1"].append(ex)
        else:
            buckets["C2"].append(ex)

    return {k: v for k, v in buckets.items() if v}


# -------------------------------------------------
# MAIN PIPELINE
# -------------------------------------------------
class WordsMasterSanitizer:

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def run(self):
        logger.info("🧹 Starting full sanitation pipeline...")

        self.cursor.execute("SELECT * FROM wordsMaster")
        rows = self.cursor.fetchall()

        updates = []

        for row in rows:
            wid = row["id"]

            word_en = normalize_text(row["wordEn"]).lower()

            definitions = clean_definitions(row["definitionEn"])
            examples_raw = clean_list_field(row["examples"], MAX_EXAMPLES * 2)
            examples = classify_examples(examples_raw)

            synonyms = clean_list_field(row["synonyms"], MAX_SYNONYMS)
            antonyms = clean_list_field(row["antonyms"], MAX_ANTONYMS)
            collocations = clean_list_field(row["collocations"], MAX_COLLOCATIONS)

            related = balance_related_words(row["relatedWords"])
            word_family = clean_word_family(row["wordFamily"])

            updates.append((
                word_en,
                json.dumps(definitions, ensure_ascii=False),
                json.dumps(examples, ensure_ascii=False),
                json.dumps(synonyms, ensure_ascii=False),
                json.dumps(antonyms, ensure_ascii=False),
                json.dumps(collocations, ensure_ascii=False),
                json.dumps(related, ensure_ascii=False),
                json.dumps(word_family, ensure_ascii=False) if word_family else None,
                wid
            ))

        self.cursor.executemany("""
            UPDATE wordsMaster SET
                wordEn = ?,
                definitionEn = ?,
                examples = ?,
                synonyms = ?,
                antonyms = ?,
                collocations = ?,
                relatedWords = ?,
                wordFamily = ?
            WHERE id = ?
        """, updates)

        self.conn.commit()
        self.conn.close()

        logger.info(f"✅ Sanitization complete. Updated {len(updates)} records.")


# -------------------------------------------------
# ENTRY POINT
# -------------------------------------------------
if __name__ == "__main__":
    DB_PATH = "WordsMaster.db"
    sanitizer = WordsMasterSanitizer(DB_PATH)
    sanitizer.run()
