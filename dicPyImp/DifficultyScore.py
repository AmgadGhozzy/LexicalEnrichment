"""
╔══════════════════════════════════════════════════════════════════════════╗
║         Difficulty Score Fixer  —  Final Version                        ║
║         Algorithm: CEFR bounds + Rank + POS + Syllables                 ║
║                                                                          ║
║  Strategy : Only fix scores OUTSIDE valid CEFR range                    ║
║  Leave alone: scores already within their CEFR range                    ║
║                                                                          ║
║  Score Drivers (in order of weight):                                     ║
║    1. CEFR bounds   → hard constraint  (floor & ceiling)                 ║
║    2. Rank position → primary driver   (~70%)                            ║
║    3. Syllable delta→ secondary        (~20%)                            ║
║    4. POS delta     → tertiary         (~10%)                            ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import shutil
import os
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# 1.  DATABASE PATH DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def find_db() -> str:
    """
    Search for WordsMaster.db in standard locations.
    Supports Android (/sdcard) and desktop (Windows / macOS / Linux).
    """
    if os.path.exists("/sdcard"):                             # Android
        candidates = [
            "/sdcard/DictionaryEnrichment/Manual/WordsMaster.db",
            "/sdcard/WordsMaster.db",
            "/storage/emulated/0/DictionaryEnrichment/Manual/WordsMaster.db",
            "/storage/emulated/0/DictionaryEnrichment/WordsMaster.db",
            "/storage/emulated/0/WordsMaster.db",
        ]
    else:                                                     # Desktop
        home = Path.home()
        candidates = [
            str(home / "Desktop"   / "DictionaryEnrichment" / "Manual" / "WordsMaster.db"),
            str(home / "Downloads" / "DictionaryEnrichment" / "Manual" / "WordsMaster.db"),
            str(home / "Downloads" / "WordsMaster.db"),
            str(home / "Desktop"   / "WordsMaster.db"),
            str(home / "Documents" / "WordsMaster.db"),
        ]

    for p in candidates:
        if os.path.exists(p):
            return p

    # Fallback: recursive home-directory search
    for root, dirs, files in os.walk(Path.home()):
        # Skip hidden folders and common large directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                   ('node_modules', '__pycache__', 'AppData', 'Library')]
        for f in files:
            if f == "WordsMaster.db":
                return os.path.join(root, f)

    return None


# ═══════════════════════════════════════════════════════════════════════════
# 2.  ALGORITHM CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

# Hard score boundaries per CEFR level — NEVER violated
CEFR_BOUNDS: dict[str, tuple[int, int]] = {
    "A1": (2, 5),
    "A2": (3, 6),
    "B1": (4, 7),
    "B2": (5, 7),
    "C1": (7, 9),
    "C2": (8, 10),
}

# POS difficulty adjustment
# Reasoning: prepositions / conjunctions demand collocational knowledge → harder
POS_DELTA: dict[str, float] = {
    "num":   -0.5,   # numbers are simple
    "pron":  -0.5,   # pronouns learned very early
    "excl":  -0.5,   # exclamations are intuitive
    "modal": -0.5,   # modals introduced early in curricula
    "det":    0.0,   # baseline
    "noun":   0.0,   # baseline
    "verb":   0.0,   # baseline
    "adj":   +0.3,   # register / degree nuance
    "adv":   +0.3,   # placement & nuance
    "prep":  +0.7,   # collocations are tricky
    "conj":  +0.7,   # sentence complexity
}

# Syllable count → difficulty delta within the CEFR range
# grandparent (3 syl, A1) should score higher than cat (1 syl, A1)
SYLLABLE_DELTA: dict[int, float] = {
    1: -0.5,   # cat, run, go          — easy to pronounce & spell
    2:  0.0,   # ta•ble, wa•ter        — standard baseline
    3: +0.4,   # um•brel•la            — noticeably longer
    4: +0.7,   # in•for•ma•tion        — long word
    5: +1.0,   # char•ac•ter•is•tic    — complex
}


# ═══════════════════════════════════════════════════════════════════════════
# 3.  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _count_syllables(syllabify_str, word: str) -> int:
    """
    Count syllables.
    Primary  : use syllabify field  (e.g.  'gran•par•ent'  → 3)
    Fallback : vowel-group estimator when syllabify is empty
    """
    if syllabify_str and "•" in str(syllabify_str):
        return len(str(syllabify_str).split("•"))

    # ── Vowel-group estimator ──────────────────────────────────────────────
    if not word:
        return 1
    w = word.lower().replace("-", "").replace(" ", "")
    vowels = "aeiouy"
    count, prev_vowel = 0, False
    for ch in w:
        v = ch in vowels
        if v and not prev_vowel:
            count += 1
        prev_vowel = v
    if w.endswith("e") and count > 1:          # silent -e  (cake, name)
        count -= 1
    if len(w) >= 3 and w.endswith("le") and w[-3] not in vowels:
        count += 1                              # -le syllable  (ta•ble)
    return max(1, count)


def _rank_position(rank) -> float:
    """
    Map frequency rank  →  0.0 – 1.0 position inside the CEFR score range.
    Lower rank (= more frequent word) → position closer to 0 (lower score).
    """
    if not rank or rank <= 0:
        return 0.5            # unknown rank → middle of range

    if rank <= 150:   return 0.00   # top-tier common  (year, man, day)
    if rank <= 400:   return 0.30   # very common      (give, turn, try)
    if rank <= 700:   return 0.50   # common           (open, foot, bear)
    if rank <= 1500:  return 0.65   # fairly common    (tree, save, lift)
    if rank <= 4000:  return 0.78   # less common      (hero, poet, coach)
    if rank <= 7000:  return 0.88   # uncommon         (sofa, tidy, hatch)
    return 1.00                     # rare              (moor, sway, whence)


def calculate_score(cefr: str, pos: str, rank,
                    syllabify=None, word: str = "") -> int:
    """
    Compute the correct difficultyScore.

    Formula:
        raw = lo  +  range × rank_position  +  pos_delta  +  syllable_delta
        score = clamp(round(raw), lo, hi)

    Always returns an integer within the CEFR valid range.
    """
    lo, hi = CEFR_BOUNDS.get(cefr.upper(), (4, 7))
    rng = hi - lo

    pos_d  = POS_DELTA.get(pos.lower(), 0.0)
    syll   = _count_syllables(syllabify, word)
    syll_d = SYLLABLE_DELTA.get(min(syll, 5), 1.0)

    raw = lo + rng * _rank_position(rank) + pos_d + syll_d
    return max(lo, min(hi, round(raw)))


def is_score_valid(cefr: str, score) -> bool:
    """Return True if score is already within the valid CEFR range."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return False
    lo, hi = CEFR_BOUNDS.get(cefr.upper(), (1, 10))
    return lo <= s <= hi


# ═══════════════════════════════════════════════════════════════════════════
# 4.  BACKUP
# ═══════════════════════════════════════════════════════════════════════════

def create_backup(db_path: str) -> str:
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path.replace(".db", f"_backup_{ts}.db")
    shutil.copy2(db_path, backup)
    return backup


# ═══════════════════════════════════════════════════════════════════════════
# 5.  ANALYSIS  (dry-run — no writes)
# ═══════════════════════════════════════════════════════════════════════════

def analyze(db_path: str) -> list:
    """
    Find all rows whose difficultyScore is OUTSIDE the valid CEFR bounds.
    Returns a list of dicts:  id, wordEn, pos, cefr, rank, syll, old, new
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    cur.execute("""
        SELECT id, wordEn, pos, cefrLevel,
               COALESCE(rank, 0)  AS rank,
               syllabify,
               difficultyScore
        FROM   wordsMaster
        WHERE  difficultyScore IS NOT NULL
          AND  cefrLevel       IS NOT NULL
          AND  pos             IS NOT NULL
        ORDER  BY cefrLevel, CAST(difficultyScore AS REAL) DESC
    """)
    rows = cur.fetchall()
    conn.close()

    to_fix = []
    for r in rows:
        cefr = str(r["cefrLevel"]).strip().upper()
        pos  = str(r["pos"]).strip().lower()
        rank = int(r["rank"]) if r["rank"] else 0
        syll = r["syllabify"]
        old  = r["difficultyScore"]
        word = r["wordEn"] or ""

        if cefr not in CEFR_BOUNDS:
            continue
        if is_score_valid(cefr, old):
            continue                        # already within bounds → skip

        new = calculate_score(cefr, pos, rank, syll, word)
        to_fix.append({
            "id":    r["id"],
            "wordEn": word,
            "pos":   pos,
            "cefr":  cefr,
            "rank":  rank,
            "syll":  _count_syllables(syll, word),
            "old":   old,
            "new":   new,
        })

    return to_fix


# ═══════════════════════════════════════════════════════════════════════════
# 6.  PREVIEW
# ═══════════════════════════════════════════════════════════════════════════

def show_preview(to_fix: list) -> None:
    W = 76
    print(f"\n{'═'*W}")
    print(f"  🔍 PREVIEW — Words with scores OUTSIDE valid CEFR bounds")
    print(f"{'═'*W}")

    if not to_fix:
        print("  ✅  Nothing to fix! All scores are within valid CEFR ranges.")
        return

    by_cefr: dict[str, list] = {}
    for r in to_fix:
        by_cefr.setdefault(r["cefr"], []).append(r)

    for cefr in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        items = by_cefr.get(cefr, [])
        if not items:
            continue
        lo, hi = CEFR_BOUNDS[cefr]
        print(f"\n  {cefr}  (valid range: {lo}–{hi})  →  {len(items)} words to fix")
        print(f"  {'Word':<16} {'POS':<6} {'Rank':<7} {'Syl':<5} {'Old':>5} →  New")
        print(f"  {'-'*52}")
        for r in items[:25]:
            print(f"  {r['wordEn']:<16} {r['pos']:<6} {r['rank']:<7} "
                  f"{r['syll']:<5} {str(r['old']):>5} →  {r['new']}")
        if len(items) > 25:
            print(f"  … and {len(items)-25} more")

    print(f"\n{'─'*W}")
    print(f"  📊 Total to fix : {len(to_fix)}")
    print(f"  📌 Strategy     : recalculate only scores outside CEFR bounds")
    print(f"  ✅ Leave alone  : all scores already within their CEFR range")
    print(f"{'─'*W}")


# ═══════════════════════════════════════════════════════════════════════════
# 7.  APPLY FIXES
# ═══════════════════════════════════════════════════════════════════════════

def apply_fixes(db_path: str, to_fix: list) -> int:
    """Write new scores to the database.  Returns number of rows updated."""
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.executemany(
        "UPDATE wordsMaster SET difficultyScore = ? WHERE id = ?",
        [(str(r["new"]), r["id"]) for r in to_fix]
    )
    conn.commit()
    conn.close()
    return len(to_fix)


# ═══════════════════════════════════════════════════════════════════════════
# 8.  SELF-TEST  (runs before any DB operation)
# ═══════════════════════════════════════════════════════════════════════════

def self_test() -> bool:
    """
    Validate the algorithm against hand-verified examples.
    Each tuple:  (word, cefr, pos, rank, syllabify, expected_score)
    """
    tests = [
        # word            cefr   pos     rank   syllabify              expected
        ("cat",          "A1",  "noun",   587,  "cat",                    2),
        ("year",         "A1",  "noun",   101,  "year",                   2),
        ("sit",          "A1",  "verb",   507,  "sit",                    3),
        ("information",  "A1",  "noun",   498,  "in•for•ma•tion",         4),
        ("grandparent",  "A1",  "noun",  3358,  "grand•par•ent",          5),
        ("sofa",         "A2",  "noun",  6225,  "so•fa",                  6),
        ("opportunity",  "A2",  "noun",   939,  "op•por•tu•ni•ty",        6),
        ("pony",         "B1",  "noun",  6481,  "po•ny",                  7),
        ("responsibility","B1", "noun",  1216,  "re•spon•si•bil•i•ty",    7),
        ("deny",         "B2",  "verb",  1799,  "de•ny",                  7),
        ("atom",         "B2",  "noun",  5386,  "at•om",                  7),
        ("fury",         "C1",  "noun",  6234,  "fu•ry",                  9),
        ("constitute",   "C1",  "verb",  2846,  "con•sti•tute",           9),
        ("par",          "C2",  "noun",  6825,  "par",                    9),
        ("affecting",    "C2",  "adj",   3995,  "af•fect•ing",           10),
    ]

    W = 76
    print(f"\n  {'Word':<16} {'CEFR':<4} {'Syl':<4} {'Score':<6} {'Expected':<9} Status")
    print(f"  {'-'*56}")
    ok = 0
    for word, cefr, pos, rank, syll, expected in tests:
        score  = calculate_score(cefr, pos, rank, syll, word)
        syll_n = _count_syllables(syll, word)
        lo, hi = CEFR_BOUNDS[cefr]
        # Accept ±1 tolerance AND must be within bounds
        in_bounds = lo <= score <= hi
        close     = abs(score - expected) <= 1
        passed    = in_bounds and close
        status    = "✅" if passed else "❌"
        if passed:
            ok += 1
        print(f"  {word:<16} {cefr:<4} {syll_n:<4} {score:<6} {expected:<9} {status}")

    total = len(tests)
    print(f"\n  Result: {ok}/{total} passed")
    return ok == total


# ═══════════════════════════════════════════════════════════════════════════
# 9.  MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    W = 76
    print(f"\n{'═'*W}")
    print("  🔢  Difficulty Score Fixer — Final Version")
    print("  📐  Algorithm: CEFR bounds + Rank + POS + Syllables")
    print(f"{'═'*W}")

    # ── Self-test ──────────────────────────────────────────────────────────
    print("\n  🧪 Running self-test …")
    if not self_test():
        print("\n  ❌ Self-test failed — aborting to protect the database.")
        return
    print("  ✅ Self-test passed\n")

    # ── Find database ──────────────────────────────────────────────────────
    db_path = find_db()
    if not db_path:
        print("  ❌ Could not find WordsMaster.db")
        print("     Place it in one of the standard locations and try again.")
        return
    print(f"  ✅ Database : {db_path}")

    # ── Analyze ────────────────────────────────────────────────────────────
    print("  🔍 Scanning …", end="", flush=True)
    to_fix = analyze(db_path)
    print(f" done.\n")

    show_preview(to_fix)

    if not to_fix:
        return

    # ── Confirm ────────────────────────────────────────────────────────────
    print("\n  ⚠️  A backup will be created automatically before any changes.\n")
    choice = input("  ▶ Apply fixes? (yes / no): ").strip().lower()
    if choice not in ("yes", "y"):
        print("\n  ⏸  Cancelled — no changes made.")
        return

    # ── Backup ─────────────────────────────────────────────────────────────
    print("\n  💾 Creating backup …", end="", flush=True)
    backup = create_backup(db_path)
    print(f" done  →  {Path(backup).name}")

    # ── Apply ──────────────────────────────────────────────────────────────
    print("  🔧 Applying fixes …", end="", flush=True)
    updated = apply_fixes(db_path, to_fix)
    print(f" done")

    print(f"\n{'═'*W}")
    print(f"  ✅ SUCCESS — {updated:,} words updated")
    print(f"  📦 Backup  — {Path(backup).name}")
    print(f"{'═'*W}\n")


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()