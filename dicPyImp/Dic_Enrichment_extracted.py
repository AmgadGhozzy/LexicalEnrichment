# 1. تثبيت المكتبات اللازمة
!pip install nltk
!pip install tqdm

import sqlite3
import json
import nltk
from nltk.corpus import wordnet as wn
from tqdm import tqdm
from google.colab import drive

# 2. تحميل بيانات NLTK الأكاديمية
nltk.download('wordnet')
nltk.download('omw-1.4')

# 3. توصيل Google Drive
drive.mount('/content/drive')

# حدد مسار قاعدة البيانات الخاص بك هنا
# Please verify this path carefully if you encounter issues opening the database.
DB_PATH = '/content/drive/MyDrive/WordsMaster.db'


class LinguisticEnricher:
    def __init__(self, db_path):
        self.db_path = db_path
        # خريطة لتحويل تصنيفات WordNet الجافة إلى تصنيفات صديقة للمستخدم
        self.category_map = {
            'noun.animal': 'Animals', 'noun.food': 'Food & Drink',
            'noun.body': 'Health & Body', 'noun.feeling': 'Emotions',
            'noun.location': 'Places & Travel', 'noun.time': 'Time',
            'noun.artifact': 'Objects & Tools', 'verb.communication': 'Communication',
            'noun.person': 'People', 'noun.group': 'Society',
            'noun.quantity': 'Math & Numbers', 'noun.state': 'Conditions',
            'noun.cognition': 'Mind & Thinking', 'noun.act': 'Actions',
            'adj.all': 'General Quality', 'adv.all': 'Manner'
        }

    def get_word_family(self, word):
        """استخراج عائلة الكلمة (Noun, Verb, Adj, Adv) باستخدام الاشتقاق"""
        family = {"noun": "", "verb": "", "adj": "", "adv": ""}
        for synset in wn.synsets(word):
            for lemma in synset.lemmas():
                # البحث عن الكلمات المشتقة من هذا الجذر
                for derived in lemma.derivationally_related_forms():
                    related_word = derived.name()
                    related_pos = derived.synset().pos()

                    if related_pos == 'n' and not family["noun"]: family["noun"] = related_word
                    elif related_pos == 'v' and not family["verb"]: family["verb"] = related_word
                    elif related_pos == 'a' and not family["adj"]: family["adj"] = related_word
                    elif related_pos == 'r' and not family["adv"]: family["adv"] = related_word
        return family

    def get_category(self, word):
        """تحديد تصنيف الكلمة بناءً على Lexical Names في WordNet"""
        synsets = wn.synsets(word)
        if not synsets:
            return "General"

        # نأخذ التصنيف الأكثر شيوعاً للمعنى الأول للكلمة
        lex_name = synsets[0].lexname()
        return self.category_map.get(lex_name, lex_name.split('.')[-1].capitalize())

    def run_enrichment(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # جلب الكلمات التي تنقصها العائلة أو التصنيف
        cursor.execute("SELECT id, wordEn FROM wordsMaster WHERE wordFamily IS NULL OR category IS NULL OR wordFamily = '{}'")
        rows = cursor.fetchall()

        print(f"🚀 Processing {len(rows)} words...")

        for row in tqdm(rows):
            word = row['wordEn']

            # توليد البيانات
            family = self.get_word_family(word)
            category = self.get_category(word)

            # تحديث قاعدة البيانات
            cursor.execute("""
                UPDATE wordsMaster
                SET wordFamily = ?, category = ?
                WHERE id = ?
            """, (json.dumps(family), category, row['id']))

            if row['id'] % 100 == 0:
                conn.commit()

        conn.commit()
        conn.close()
        print("\n✅ Enrichment Complete!")

# تشغيل العملية
enricher = LinguisticEnricher(DB_PATH)
enricher.run_enrichment()


import nltk
from nltk.corpus import wordnet as wn
from nltk.corpus import cmudict

# تحميل المصادر الضرورية
nltk.download('wordnet')
nltk.download('omw-1.4')
nltk.download('cmudict')
nltk.download('averaged_perceptron_tagger')

d = cmudict.dict() # قاموس النطق والتقطيع

import nltk
from nltk.corpus import wordnet as wn

def analyze_multitask_word(word):
    synsets = wn.synsets(word)
    pos_map = {'n': 'Noun', 'v': 'Verb', 'a': 'Adjective', 'r': 'Adverb'}

    analysis = {}

    for syn in synsets:
        pos_code = syn.pos()
        pos_name = pos_map.get(pos_code, pos_code)

        if pos_name not in analysis:
            analysis[pos_name] = {
                "definition": syn.definition(),
                "example": syn.examples()[0] if syn.examples() else "No example"
            }

    return analysis

# تجربة كلمة "Fast"
result = analyze_multitask_word("fast")
import json
print(json.dumps(result, indent=2))

def get_linguistic_intelligence(word):
    # 1. استخراج عدد المقاطع الصوتية (Syllables) بدقة
    try:
        syllable_count = [len(list(y for y in x if y[-1].isdigit())) for x in d[word.lower()]][0]
    except:
        syllable_count = "N/A"

    # 2. استخراج المترادفات والأضداد من WordNet
    synonyms = []
    antonyms = []
    definition = ""

    for syn in wn.synsets(word):
        definition = syn.definition() # أخذ أول تعريف أكاديمي
        for l in syn.lemmas():
            synonyms.append(l.name())
            if l.antonyms():
                antonyms.append(l.antonyms()[0].name())

    return {
        "Word": word,
        "Definition": definition,
        "Syllables": syllable_count,
        "Synonyms": list(set(synonyms))[:], # أهم 3 مترادفات
        "Antonyms": list(set(antonyms))[:]  # أهم ضدين
    }

# تجربة المختبر
result = get_linguistic_intelligence("fast")
print(result)


import nltk
from nltk.corpus import wordnet as wn

def get_word_senses_with_categories(word):
    synsets = wn.synsets(word)
    senses = []

    for syn in synsets:
        # الـ lexname يعطيك التصنيف الأكاديمي للمعنى بدقة
        # مثل: noun.food, adj.all, verb.consumption
        raw_category = syn.lexname()

        sense_data = {
            "pos": syn.pos(),
            "definition": syn.definition(),
            "raw_category": raw_category,
            "example": syn.examples()[0] if syn.examples() else ""
        }
        senses.append(sense_data)

    return senses

# تجربة كلمة fast
results = get_word_senses_with_categories("fast")
for r in results:
    print(f"POS: {r['pos']} | Category: {r['raw_category']} | Def: {r['definition'][:40]}...")

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║   WordsMaster — Smart Re-Ranking Pipeline  (Google Colab)              ║
# ║                                                                         ║
# ║   Pipeline (4 stages, runs in order):                                  ║
# ║     Stage 1 — Global re-rank by real-world frequency (wordfreq)        ║
# ║     Stage 2 — Reorder duplicate groups by POS frequency                ║
# ║     Stage 3 — Space duplicate copies 150 ranks apart                   ║
# ║     Stage 4 — Sync: rank = id (clean sequential IDs)                   ║
# ║                                                                         ║
# ║   Usage:                                                                ║
# ║     1. Run CELL 1 (install + mount)                                    ║
# ║     2. Run CELL 2 (config — set DB_PATH)                               ║
# ║     3. Run CELL 3 (pipeline functions)                                  ║
# ║     4. Run CELL 4 (dry-run preview — no DB changes)                    ║
# ║     5. Run CELL 5 (apply — writes to DB after confirmation)            ║
# ╚══════════════════════════════════════════════════════════════════════════╝


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 1 — Install dependencies & mount Google Drive
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

!pip install -q wordfreq

from google.colab import drive
drive.mount('/content/drive')
print("✅ Drive mounted.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 2 — Configuration  (only thing you need to edit)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DB_PATH = "/content/drive/MyDrive/WordsMaster.db"   # ← عدّل هنا لو احتجت

# الفجوة بين نسخ الكلمة المكررة — تزيد بزيادة صعوبة المستوى
# المنطق: الكلمة الصعبة (C1/C2) محتاج وقت أطول قبل ما المستخدم يشوفها تاني
CEFR_SPACING = {
    "A1": 100,   # شائعة جداً، مش مشكلة لو اتكررت قريب
    "A2": 150,
    "B1": 200,
    "B2": 300,
    "C1": 400,
    "C2": 500,   # نادرة، محتاج تتباعد كتير
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 3 — Pipeline functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import sqlite3
import shutil
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from wordfreq import zipf_frequency, word_frequency

# ── Constants ─────────────────────────────────────────────────────────────

# POS display priority — used only as a tie-breaker in Stage 1
# (lower number = shown first when two words have equal zipf score)
POS_TIEBREAK = {
    'det': 1, 'pron': 2, 'conj': 3, 'prep': 4,
    'noun': 5, 'verb': 6, 'modal': 6,
    'adj': 7, 'adv': 8, 'num': 9, 'excl': 10,
}

# wordfreq POS tags for Stage 2 (POS-specific frequency lookup)
WORDFREQ_POS = {
    "noun":  "noun",
    "verb":  "verb",
    "modal": "verb",
    "adj":   "adjective",
    "adv":   "adverb",
    # prep/conj/pron/det/num/excl → no POS-specific lookup in wordfreq
}

# Fallback corpus ratios for POS types wordfreq can't distinguish
# (based on COCA + BNC research — relative frequency of each POS)
POS_CORPUS_RATIO = {
    "verb":  1.00, "modal": 0.98, "conj": 0.95, "prep": 0.93,
    "pron":  0.92, "det":   0.90, "noun": 0.88, "adv":  0.75,
    "adj":   0.70, "num":   0.65, "excl": 0.40,
}


# ── Helpers ───────────────────────────────────────────────────────────────

def _backup(db_path: str, tag: str) -> str:
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path.replace(".db", f"_backup_{tag}_{ts}.db")
    shutil.copy2(db_path, backup)
    return backup


def _pos_freq(word: str, pos: str) -> float:
    """POS-aware frequency score for a word (used in Stage 2)."""
    wf_pos = WORDFREQ_POS.get(pos)
    if wf_pos:
        try:
            f = word_frequency(word, 'en', wordlist='large', pos=wf_pos)
            if f > 0:
                return f
        except Exception:
            pass
    overall = word_frequency(word, 'en', wordlist='large')
    return overall * POS_CORPUS_RATIO.get(pos, 0.5)


def _section(title: str):
    print(f"\n{'═'*68}")
    print(f"  {title}")
    print(f"{'═'*68}")


def _load_all(cursor) -> list:
    """Load every row ordered by current rank."""
    cursor.execute("SELECT id, wordEn, pos, cefrLevel, rank FROM wordsMaster ORDER BY rank ASC")
    return [{"id": r[0], "word": r[1], "pos": (r[2] or "noun").lower(),
             "cefr": (r[3] or "B1").upper(), "rank": r[4]}
            for r in cursor.fetchall()]


# ── Stage 1: Global frequency re-rank ─────────────────────────────────────

def stage1_global_rerank(rows: list) -> list:
    """
    Assign a new rank to every word based on its real-world Zipf frequency.
    Words with higher Zipf score → smaller (better) rank.
    POS is used only as a tie-breaker for identical words.
    Returns rows with an updated 'rank' field.
    """
    _section("Stage 1 — Global Re-Rank by Frequency (wordfreq)")
    print(f"  Computing Zipf frequency for {len(rows)} words …\n")

    for r in rows:
        r["zipf"]     = zipf_frequency(r["word"], 'en')
        r["tiebreak"] = POS_TIEBREAK.get(r["pos"], 10)

    # Sort: highest Zipf first; same Zipf → POS tiebreak
    rows.sort(key=lambda x: (-x["zipf"], x["tiebreak"]))

    # Assign sequential ranks
    for i, r in enumerate(rows, 1):
        r["old_rank"] = r["rank"]
        r["rank"]     = i

    # Preview (first 20)
    print(f"  {'Word':<16} {'POS':<7} {'Old Rank':>10} {'New Rank':>10}  {'Zipf'}")
    print(f"  {'─'*58}")
    for r in rows[:20]:
        changed = " ←" if r["rank"] != r["old_rank"] else ""
        print(f"  {r['word']:<16} {r['pos']:<7} {r['old_rank']:>10} {r['rank']:>10}  {r['zipf']:.3f}{changed}")
    if len(rows) > 20:
        print(f"  … {len(rows)-20} more rows")

    changed = sum(1 for r in rows if r["rank"] != r["old_rank"])
    print(f"\n  📊 Rows with changed rank : {changed} / {len(rows)}")
    return rows


# ── Stage 2: POS ordering for duplicate groups ────────────────────────────

def stage2_pos_ordering(rows: list) -> list:
    """
    Within each duplicate word group, reorder the entries so the most
    frequently used POS gets the lower (better) rank.

    Example:  'that' as conj is more common than 'that' as pron/det
              → conj gets the lowest rank number.
    """
    _section("Stage 2 — POS Ordering for Duplicate Groups")

    # Group by word
    groups = defaultdict(list)
    for r in rows:
        groups[r["word"]].append(r)

    duplicates = {w: g for w, g in groups.items() if len(g) > 1}
    print(f"  Duplicate word groups found : {len(duplicates)}\n")
    print(f"  {'Word':<16} {'Old order':<36}  New order")
    print(f"  {'─'*70}")

    changed_groups = 0

    for word, group in duplicates.items():
        # Current ranks assigned to this group
        current_ranks = sorted(r["rank"] for r in group)

        # Score each entry by POS-specific frequency
        for r in group:
            r["_pos_freq"] = _pos_freq(word, r["pos"])

        # Sort group: highest POS frequency → lowest (best) rank
        group_sorted = sorted(group, key=lambda x: x["_pos_freq"], reverse=True)

        old_str = " | ".join(f"{r['pos']}={r['rank']}" for r in group)
        any_change = False

        for entry, new_rank in zip(group_sorted, current_ranks):
            if entry["rank"] != new_rank:
                any_change = True
            entry["rank"] = new_rank

        if any_change:
            changed_groups += 1
            new_str = " | ".join(f"{r['pos']}={r['rank']}" for r in group_sorted)
            print(f"  {word:<16} {old_str:<36}  {new_str}")

    print(f"\n  📊 Groups reordered : {changed_groups} / {len(duplicates)}")

    # Flatten back to a flat list sorted by rank
    rows_out = [r for group in groups.values() for r in group]
    rows_out.sort(key=lambda x: x["rank"])
    return rows_out


# ── Stage 3: Duplicate spacing (CEFR-aware) ──────────────────────────────

def stage3_spacing(rows: list, cefr_spacing: dict = None) -> list:
    """
    Push duplicate copies of the same word apart — gap size depends on
    the CEFR level of the word (harder words = larger gap).

    Rationale:
      A1 words (100 gap): very common, seeing them again soon is fine.
      C1/C2 words (400/500 gap): rare and hard — user needs more unique
      words between encounters to avoid confusion/frustration.

    Algorithm:
      1. The first occurrence of each word keeps its rank as anchor.
      2. The CEFR of the first occurrence defines the spacing for the group.
      3. 2nd copy → sort_key = anchor + 1 × CEFR_spacing
         3rd copy → sort_key = anchor + 2 × CEFR_spacing   etc.
      4. All entries sorted by sort_key, then re-numbered 1..N.
    """
    if cefr_spacing is None:
        cefr_spacing = CEFR_SPACING

    spacing_label = " | ".join(f"{k}={v}" for k, v in cefr_spacing.items())
    _section(f"Stage 3 — CEFR-Aware Duplicate Spacing")
    print(f"  Spacing per level: {spacing_label}\n")

    word_anchor  = {}              # word → rank of first occurrence
    word_cefr    = {}              # word → CEFR of first occurrence
    word_seen    = defaultdict(int)

    for r in rows:
        w    = r["word"]
        cefr = r.get("cefr", "B1")

        if w not in word_anchor:
            word_anchor[w] = r["rank"]
            word_cefr[w]   = cefr          # ← CEFR of first occurrence = group anchor
            r["_sort_key"] = r["rank"]
            r["_nth"]      = 0
            r["_gap"]      = 0
        else:
            nth            = word_seen[w]
            anchor_cefr    = word_cefr[w]  # ← always use anchor's CEFR for the gap
            gap            = cefr_spacing.get(anchor_cefr, 200)
            r["_sort_key"] = word_anchor[w] + nth * gap
            r["_nth"]      = nth
            r["_gap"]      = gap
        word_seen[w] += 1

    # Sort by sort_key (tie-break on original rank)
    rows.sort(key=lambda x: (x["_sort_key"], x["rank"]))

    # Re-number 1..N
    for i, r in enumerate(rows, 1):
        r["old_rank"] = r["rank"]
        r["rank"]     = i

    # ── Display affected groups ────────────────────────────────────────
    affected_words = {r["word"] for r in rows if r["_nth"] > 0}
    word_rows      = defaultdict(list)
    for r in rows:
        if r["word"] in affected_words:
            word_rows[r["word"]].append(r)

    print(f"  Duplicate groups spaced : {len(affected_words)}\n")
    print(f"  {'Word':<16} {'CEFR':<5} {'Gap':>5} {'POS':<7} {'Old':>8} {'New':>8}  {'Shift':>7}")
    print(f"  {'─'*65}")

    shown = 0
    for word, group in sorted(word_rows.items(), key=lambda x: x[1][0]["rank"]):
        for r in sorted(group, key=lambda x: x["rank"]):
            shift = r["rank"] - r["old_rank"]
            tag   = f"[dup #{r['_nth']+1}]" if r["_nth"] > 0 else ""
            cefr  = word_cefr.get(word, "?")
            gap   = r["_gap"] if r["_nth"] > 0 else "—"
            print(f"  {word:<16} {cefr:<5} {str(gap):>5} {r['pos']:<7} "
                  f"{r['old_rank']:>8} {r['rank']:>8}  {shift:>+7}  {tag}")
        print()
        shown += 1
        if shown >= 25:
            print(f"  … and {len(affected_words)-25} more groups\n")
            break

    changed = sum(1 for r in rows if r["rank"] != r["old_rank"])
    print(f"  📊 Total rows shifted : {changed}")
    return rows


# ── Stage 4: Sync rank = id ───────────────────────────────────────────────

def stage4_sync_id(rows: list) -> list:
    """
    After all re-ranking, ensure id == rank for every row.
    Rebuilds the table via a temp table to avoid UNIQUE constraint conflicts.
    (This stage runs only on the DB, not on the in-memory list.)
    """
    _section("Stage 4 — Sync: id = rank")
    print("  Final ranks are clean integers 1..N")
    print("  id will be updated to match rank exactly.\n")
    # Actual DB work happens inside run_pipeline() after all stages.
    return rows


# ── Master pipeline ───────────────────────────────────────────────────────

def run_pipeline(dry_run: bool = True):
    """
    dry_run = True  → compute everything, print preview, no DB writes
    dry_run = False → apply all stages to the DB (with backup first)
    """

    mode_label = "DRY RUN — preview only, no changes" if dry_run else "🔧 APPLY — writing to database"
    print(f"\n{'╔'+'═'*66+'╗'}")
    print(f"║  {'WordsMaster Re-Ranking Pipeline':<64}║")
    print(f"║  Mode: {mode_label:<58}║")
    print(f"{'╚'+'═'*66+'╝'}")

    if not Path(DB_PATH).exists():
        print(f"\n❌ Database not found: {DB_PATH}")
        return

    # ── Connect & load ─────────────────────────────────────────────────
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    rows   = _load_all(cursor)
    conn.close()

    print(f"\n  ✅ Database : {DB_PATH}")
    print(f"  📊 Total rows : {len(rows)}")

    # ── Run the 4 stages in memory ─────────────────────────────────────
    rows = stage1_global_rerank(rows)
    rows = stage2_pos_ordering(rows)
    rows = stage3_spacing(rows, CEFR_SPACING)
    rows = stage4_sync_id(rows)        # preview only — DB work below

    # ── Summary ────────────────────────────────────────────────────────
    _section("Pipeline Summary")
    changed_total = sum(1 for r in rows if r["rank"] != r.get("old_rank", r["rank"]))
    print(f"  Rows with new rank (vs original) : {changed_total}")
    print(f"\n  Final rank sample (first 30):")
    print(f"  {'Rank':>6}  {'Word':<18} {'POS':<8}")
    print(f"  {'─'*36}")
    for r in rows[:30]:
        print(f"  {r['rank']:>6}  {r['word']:<18} {r['pos']:<8}")

    if dry_run:
        print(f"\n  ℹ️  Dry run complete — no changes made.")
        print(f"     Run: run_pipeline(dry_run=False)  to apply.")
        return

    # ── Confirm ────────────────────────────────────────────────────────
    print()
    confirm = input("  ▶ Apply all changes to database? (yes / no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("  ⏸  Cancelled — no changes made.")
        return

    # ── Backup ─────────────────────────────────────────────────────────
    print("\n  💾 Creating backup …", end="", flush=True)
    backup = _backup(DB_PATH, "pipeline")
    print(f" done  →  {Path(backup).name}")

    # ── Apply Stage 1-3: update rank for every row ────────────────────
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("  🔧 Applying rank updates …", end="", flush=True)
    rank_updates = [(r["rank"], r["id"]) for r in rows]
    cursor.executemany("UPDATE wordsMaster SET rank = ? WHERE id = ?", rank_updates)
    conn.commit()
    print(f" done  ({len(rank_updates)} rows)")

    # ── Apply Stage 4: rebuild table so id = rank ─────────────────────
    print("  🔄 Rebuilding table (id = rank) …", end="", flush=True)

    cursor.execute("PRAGMA table_info(wordsMaster)")
    col_names = [c[1] for c in cursor.fetchall()]

    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='wordsMaster'")
    create_sql = cursor.fetchone()[0]
    create_temp = create_sql.replace("wordsMaster", "wordsMaster_temp", 1)

    cursor.execute("DROP TABLE IF EXISTS wordsMaster_temp")
    cursor.execute(create_temp)

    cursor.execute(f"SELECT {', '.join(col_names)} FROM wordsMaster ORDER BY rank ASC")
    old_rows = cursor.fetchall()

    id_idx   = col_names.index("id")
    rank_idx = col_names.index("rank")

    new_rows = []
    for row in old_rows:
        row_list         = list(row)
        row_list[id_idx] = row_list[rank_idx]   # id ← rank
        new_rows.append(tuple(row_list))

    placeholders = ", ".join(["?"] * len(col_names))
    cursor.executemany(f"INSERT INTO wordsMaster_temp VALUES ({placeholders})", new_rows)

    cursor.execute("DROP TABLE wordsMaster")
    cursor.execute("ALTER TABLE wordsMaster_temp RENAME TO wordsMaster")
    conn.commit()
    conn.close()
    print(" done")

    # ── VACUUM ─────────────────────────────────────────────────────────
    print("  🧹 VACUUM …", end="", flush=True)
    conn_v = sqlite3.connect(DB_PATH)
    conn_v.execute("VACUUM")
    conn_v.close()
    print(" done")

    # ── Final verification ─────────────────────────────────────────────
    conn_c  = sqlite3.connect(DB_PATH)
    sample  = conn_c.execute(
        "SELECT id, rank, wordEn, pos FROM wordsMaster ORDER BY rank LIMIT 10"
    ).fetchall()
    dup_check = conn_c.execute("""
        SELECT wordEn, MIN(rank), MAX(rank)
        FROM wordsMaster
        GROUP BY wordEn
        HAVING COUNT(*) > 1
        ORDER BY MIN(rank)
        LIMIT 5
    """).fetchall()
    conn_c.close()

    print(f"\n  🔍 Verification — first 10 rows (id should = rank):")
    print(f"  {'id':>6}  {'rank':>6}  {'Word':<18} {'POS':<8} {'id=rank?'}")
    print(f"  {'─'*50}")
    all_ok = True
    for row_id, rank, word, pos in sample:
        ok = "✅" if row_id == rank else "❌"
        if row_id != rank: all_ok = False
        print(f"  {row_id:>6}  {rank:>6}  {word:<18} {pos:<8} {ok}")

    print(f"\n  🔍 Duplicate spacing check (first 5 groups):")
    print(f"  {'Word':<18} {'Min rank':>10} {'Max rank':>10} {'Gap':>8}")
    print(f"  {'─'*50}")
    for word, min_r, max_r in dup_check:
        print(f"  {word:<18} {min_r:>10} {max_r:>10} {max_r-min_r:>8}")

    print(f"\n{'═'*68}")
    if all_ok:
        print(f"  ✅ Pipeline complete — all id values match their rank.")
    else:
        print(f"  ⚠️  Some id/rank mismatches — check the data.")
    print(f"  📦 Backup : {Path(backup).name}")
    print(f"{'═'*68}\n")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 4 — Dry run (preview, no DB changes)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

run_pipeline(dry_run=False)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 5 — Apply  (uncomment when satisfied with the preview above)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# run_pipeline(dry_run=False)

"""
╔══════════════════════════════════════════════════════════════════════════╗
║     Create levels + units tables  &  Assign unitId to wordsMaster       ║
║                                                                          ║
║  Creates:                                                                ║
║    TABLE levels   →  6 rows  (A1–C2)                                    ║
║    TABLE units    →  ~108 rows                                           ║
║    COLUMN wordsMaster.unitId  →  FK to units                            ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import shutil
import os
from datetime import datetime
from pathlib import Path

DB_PATH   = "/content/drive/MyDrive/WordsMaster.db"
WORDS_PER_UNIT = 50   # كلمات فريدة لكل وحدة

LEVELS = [
    ("A1", 1, "Beginner"),
    ("A2", 2, "Elementary"),
    ("B1", 3, "Intermediate"),
    ("B2", 4, "Upper-Intermediate"),
    ("C1", 5, "Advanced"),
    ("C2", 6, "Mastery"),
]

# ═══════════════════════════════════════════════════════════════════════════

def backup(db_path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = db_path.replace(".db", f"_backup_{ts}.db")
    shutil.copy2(db_path, dst)
    return dst


def run():
    if not os.path.exists(DB_PATH):
        print(f"❌ Not found: {DB_PATH}")
        return

    print("💾 Backup …", end="", flush=True)
    bk = backup(DB_PATH)
    print(f" {Path(bk).name}\n")

    conn   = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur    = conn.cursor()

    try:
        # ── 1. Create TABLE levels ─────────────────────────────────────────
        cur.execute("DROP TABLE IF EXISTS levels")
        cur.execute("""
            CREATE TABLE levels (
                levelId     TEXT PRIMARY KEY,   -- 'A1','A2',...,'C2'
                levelOrder  INTEGER NOT NULL,   -- 1..6
                levelName   TEXT NOT NULL,      -- 'Beginner',...
                totalUnits  INTEGER DEFAULT 0,
                totalWords  INTEGER DEFAULT 0
            )
        """)
        cur.executemany(
            "INSERT INTO levels (levelId, levelOrder, levelName) VALUES (?,?,?)",
            LEVELS
        )
        print("✅ TABLE levels created (6 rows)")

        # ── 2. Create TABLE units ──────────────────────────────────────────
        cur.execute("DROP TABLE IF EXISTS units")
        cur.execute("""
            CREATE TABLE units (
                unitId      TEXT PRIMARY KEY,   -- 'A1_01','B2_15',...
                levelId     TEXT NOT NULL REFERENCES levels(levelId),
                unitOrder   INTEGER NOT NULL,   -- 1,2,3... within level
                totalWords  INTEGER DEFAULT 0
            )
        """)
        print("✅ TABLE units created")

        # ── 3. Add unitId column to wordsMaster if missing ─────────────────
        cur.execute("PRAGMA table_info(wordsMaster)")
        cols = [r[1] for r in cur.fetchall()]
        if "unitId" not in cols:
            cur.execute("ALTER TABLE wordsMaster ADD COLUMN unitId TEXT")
            print("✅ Column wordsMaster.unitId added")
        else:
            print("ℹ️  Column unitId already exists (will overwrite)")

        cur.execute("UPDATE wordsMaster SET unitId = NULL")

        # ── 4. Assign units per CEFR ───────────────────────────────────────
        print(f"\n{'═'*60}")
        print(f"  {'CEFR':<6} {'Unique':<9} {'Units':<7} {'≈Words/Unit':<13} IDs")
        print(f"{'─'*60}")

        all_units = []   # (unitId, levelId, unitOrder, totalWords)

        for levelId, levelOrder, levelName in LEVELS:

            # كلمات فريدة مرتبة بـ أصغر rank في هذا المستوى
            cur.execute("""
                SELECT wordEn, MIN(rank) as min_rank
                FROM wordsMaster
                WHERE cefrLevel = ?
                GROUP BY wordEn
                ORDER BY min_rank ASC
            """, (levelId,))
            unique_words = cur.fetchall()   # [(wordEn, min_rank), ...]

            if not unique_words:
                print(f"  {levelId:<6} 0")
                continue

            n_unique = len(unique_words)
            n_units  = -(-n_unique // WORDS_PER_UNIT)   # ceiling division
            actual   = n_unique / n_units                # words per unit (float)

            first_id = f"{levelId}_{1:02d}"
            last_id  = f"{levelId}_{n_units:02d}"
            print(f"  {levelId:<6} {n_unique:<9} {n_units:<7} ~{actual:<13.0f} {first_id}..{last_id}")

            # تعيين unit لكل كلمة فريدة
            unit_word_counts = {}   # unitId → count of unique words

            for idx, (word_en, _) in enumerate(unique_words):
                unit_num = int(idx / actual) + 1
                unit_num = min(unit_num, n_units)
                unit_id  = f"{levelId}_{unit_num:02d}"

                unit_word_counts[unit_id] = unit_word_counts.get(unit_id, 0) + 1

                # تحديث كل صفوف هذه الكلمة في هذا المستوى
                cur.execute("""
                    UPDATE wordsMaster
                    SET unitId = ?
                    WHERE wordEn = ? AND cefrLevel = ?
                """, (unit_id, word_en, levelId))

            # جمع بيانات الوحدات
            for u_num in range(1, n_units + 1):
                uid = f"{levelId}_{u_num:02d}"
                all_units.append((uid, levelId, u_num, unit_word_counts.get(uid, 0)))

        print(f"{'═'*60}")
        print(f"  Total units: {len(all_units)}\n")

        # ── 5. Insert units rows ───────────────────────────────────────────
        cur.executemany(
            "INSERT INTO units (unitId, levelId, unitOrder, totalWords) VALUES (?,?,?,?)",
            all_units
        )
        print(f"✅ Inserted {len(all_units)} rows into units table")

        # ── 6. Update levels totals ────────────────────────────────────────
        for levelId, *_ in LEVELS:
            cur.execute(
                "UPDATE levels SET totalUnits = (SELECT COUNT(*) FROM units WHERE levelId=?) WHERE levelId=?",
                (levelId, levelId)
            )
            cur.execute(
                "UPDATE levels SET totalWords = (SELECT COUNT(*) FROM wordsMaster WHERE cefrLevel=?) WHERE levelId=?",
                (levelId, levelId)
            )

        conn.commit()

        # ── 7. Summary ────────────────────────────────────────────────────
        print(f"\n📊 LEVELS TABLE:")
        print(f"  {'levelId':<7} {'Order':<7} {'Name':<22} {'Units':<7} {'Words'}")
        print(f"  {'─'*55}")
        cur.execute("SELECT levelId, levelOrder, levelName, totalUnits, totalWords FROM levels ORDER BY levelOrder")
        for row in cur.fetchall():
            print(f"  {row[0]:<7} {row[1]:<7} {row[2]:<22} {row[3]:<7} {row[4]}")

        print(f"\n📋 UNITS SAMPLE (first 5 + last 3):")
        print(f"  {'unitId':<10} {'levelId':<9} {'order':<7} {'words'}")
        print(f"  {'─'*35}")
        cur.execute("SELECT unitId, levelId, unitOrder, totalWords FROM units ORDER BY levelId, unitOrder")
        rows = cur.fetchall()
        for r in rows[:5]:
            print(f"  {r[0]:<10} {r[1]:<9} {r[2]:<7} {r[3]}")
        print(f"  ...")
        for r in rows[-3:]:
            print(f"  {r[0]:<10} {r[1]:<9} {r[2]:<7} {r[3]}")

        # ── 8. NULL check ──────────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM wordsMaster WHERE unitId IS NULL")
        nulls = cur.fetchone()[0]
        print(f"\n  {'✅ All rows assigned' if nulls==0 else f'⚠️ {nulls} rows still NULL'}")

        # ── 9. Quick queries example ───────────────────────────────────────
        print(f"""
📖 USEFUL QUERIES:
  -- كل المستويات
  SELECT * FROM levels ORDER BY levelOrder;

  -- وحدات مستوى معين
  SELECT * FROM units WHERE levelId='B1' ORDER BY unitOrder;

  -- كلمات وحدة معينة
  SELECT wordEn, pos, difficultyScore
  FROM wordsMaster WHERE unitId='B1_03' ORDER BY rank;

  -- كلمات المستوى كاملاً مرتبة بوحداتها
  SELECT u.unitId, u.unitOrder, w.wordEn, w.rank
  FROM wordsMaster w JOIN units u ON w.unitId=u.unitId
  WHERE u.levelId='A1'
  ORDER BY u.unitOrder, w.rank;
""")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        conn.close()

    # VACUUM
    print("🧹 VACUUM …", end="", flush=True)
    cv = sqlite3.connect(DB_PATH)
    cv.execute("VACUUM")
    cv.close()
    print(" done")

    print(f"\n✅ All done!  Backup → {Path(bk).name}\n")


if __name__ == "__main__":
    run()