import sqlite3
from collections import Counter

DB_PATH = "/sdcard/DictionaryEnrichment/WordsMaster.db"

# خريطة الربط (المفتاح هو الاسم الكامل : القيمة هي الاختصار)
# قمنا بتنظيمها بحيث يكون أول مفتاح لكل مجموعة هو "الاسم الأساسي" للرجوع إليه عند فك الاختصار
POS_DATA = {
    "noun": "noun",
    "numeral": "num",
    "number": "num",
    "ordinal number": "num",
    
    "verb": "verb",
    "auxiliary verb": "verb",
    "linking verb": "verb",
    "infinitive marker": "verb",
    
    "adjective": "adj",
    "adverb": "adv",
    "preposition": "prep",
    "conjunction": "conj",
    "pronoun": "pron",
    "possessive pronoun": "pron",
    "determiner": "det",
    "definite article": "det",
    "indefinite article": "det",
    "modal verb": "modal",
    "exclamation": "excl",
    "interjection": "excl",
}

# عكس الخريطة للتحويل من الاختصار للاسم الكامل (يأخذ أول ظهور كاسم أساسي)
REVERSE_MAPPING = {}
for full, abbr in POS_DATA.items():
    if abbr not in REVERSE_MAPPING:
        REVERSE_MAPPING[abbr] = full

def transform_pos(value: str, to_full: bool = True) -> str | None:
    """
    to_full = True: يحول 'adj' إلى 'adjective'
    to_full = False: يحول 'adjective' إلى 'adj'
    """
    if not value:
        return None
    
    val_clean = value.strip().lower()
    
    if to_full:
        # إذا كان المدخل اختصاراً، أرجعه لأصله، وإذا كان أصلاً كاملاً اتركه
        if val_clean in REVERSE_MAPPING:
            return REVERSE_MAPPING[val_clean]
        return val_clean # ربما هو كامل بالفعل
    else:
        # إذا كان المدخل اسماً كاملاً، حوله لاختصار
        return POS_DATA.get(val_clean, val_clean)

def run_normalization(to_full: bool = True):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id, pos FROM wordsMaster")
    rows = cur.fetchall()

    before = Counter()
    after = Counter()
    updates = []

    mode_text = "TO FULL NAME" if to_full else "TO ABBREVIATION"

    for row_id, pos in rows:
        if not pos: continue

        pos_clean = pos.strip().lower()
        before[pos_clean] += 1

        normalized = transform_pos(pos_clean, to_full=to_full)
        if not normalized: continue

        after[normalized] += 1

        if normalized != pos_clean:
            updates.append((normalized, row_id))

    print("=" * 60)
    print(f"📊 POS NORMALIZATION REPORT [{mode_text}]")
    print("=" * 60)
    
    # عرض عينة من التغييرات قبل التنفيذ
    print(f"Total Records: {len(rows)}")
    print(f"To be Updated: {len(updates)}")
    print("-" * 30)

    if updates:
        cur.executemany("UPDATE wordsMaster SET pos = ? WHERE id = ?", updates)
        conn.commit()
        print("✅ Database updated successfully.")
    else:
        print("ℹ️ No changes needed.")

    conn.close()

if __name__ == "__main__":
    # لتغيير الوضع:
    # True = يحول adj -> adjective (مناسب للعرض أو لـ Gemini)
    # False = يحول adjective -> adj (مناسب لتوفير المساحة)
    run_normalization(to_full=True)