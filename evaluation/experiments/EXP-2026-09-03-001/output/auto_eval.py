import sys, io, json, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PRED = r"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\experiments\EXP-2026-09-03-001\output\predictions.jsonl"
GOLD = r"C:\Users\HP\Desktop\LexicalEnrichment\golden_set\golden_v2.json"

# PILOT manifest corrections: id -> corrected pos
POS_CORR = {"474": "verb", "1071": "noun", "2532": "adj", "5167": "verb", "5433": "verb", "5496": "verb"}

def load_preds(path):
    out = {}
    for l in open(path, encoding="utf-8"):
        if not l.strip():
            continue
        rec = json.loads(l)
        key = rec.get("key", "")
        m = re.search(r"CAND-(\d+)$", key)
        if not m:
            continue
        wid = m.group(1)
        resp = rec.get("response") or {}
        cands = resp.get("candidates") or []
        text = ""
        if cands:
            parts = (cands[0].get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts if p.get("text"))
        obj = None
        parse_err = None
        if text:
            fm = re.search(r"\{.*\}", text, re.S)
            try:
                obj = json.loads(fm.group(0) if fm else text.strip())
            except Exception as e:
                parse_err = str(e)[:200]
        out[wid] = {"key": key, "raw": rec, "obj": obj, "parse_err": parse_err}
    return out

def load_gold(path):
    return {str(e["id"]): e for e in json.load(open(path, encoding="utf-8"))}

preds = load_preds(PRED)
gold = load_gold(GOLD)

def norm_pos(p):
    return (p or "").strip().lower()

def tokenize_words(s):
    return set(re.findall(r"[A-Za-z]+", s.lower()))

def strip_wf_dashes(s):
    # word_family forms may carry FW markers
    return (s or "").strip()

rows = []
for wid in sorted(preds.keys(), key=int):
    p = preds[wid]
    g = gold.get(wid, {})
    row = {"wid": wid, "word": g.get("wordEn"), "gold_pos_orig": g.get("pos"),
           "gold_pos_corr": POS_CORR.get(wid, g.get("pos")), "gold_cefr": g.get("cefrLevel")}
    row["parse_err"] = p["parse_err"]
    o = p["obj"]
    row["obj"] = o
    row["issues"] = []

    if o is None:
        row["issues"].append("NO_PARSE")
        rows.append(row)
        continue

    # ---- Schema / structural compliance ----
    SCHEMA_REQ = ["id","lemma","pos","cefr_level","difficulty_score","category","ai_confidence",
                  "phonetic_us","phonetic_uk","phonetic_ar","definition_en","explanation_ar",
                  "examples","mnemonic_ar","senses","collocations","synonyms","antonyms",
                  "related_words","word_family","translations"]
    missing = [k for k in SCHEMA_REQ if k not in o]
    if missing:
        row["issues"].append("MISSING_FIELDS:" + ",".join(missing))

    # id preservation
    if str(o.get("id")) != wid:
        row["issues"].append(f"ID_MISMATCH:pred={o.get('id')}!=gold={wid}")
    # pos preservation (against corrected)
    if norm_pos(o.get("pos")) != norm_pos(row["gold_pos_corr"]):
        row["issues"].append(f"POS_MISMATCH:pred={o.get('pos')}!=corr={row['gold_pos_corr']}(orig {row['gold_pos_orig']})")
    # cefr preservation
    if (o.get("cefr_level") or "").upper() != (row["gold_cefr"] or "").upper():
        row["issues"].append(f"CEFR_MISMATCH:pred={o.get('cefr_level')}!=gold={row['gold_cefr']}")

    # difficulty_score is string 1-10
    ds = o.get("difficulty_score")
    if not (isinstance(ds, str) and re.fullmatch(r"[1-9]|10", ds)):
        row["issues"].append(f"DIFFICULTY_BAD:{ds!r}")

    # category enum
    CATS = ["General / Common","Social Life & Communication","Work & Business","Actions & Processes",
            "Objects & Tools","Mind & Thinking","Numbers, Time & Math","Food & Drink","Travel & Movement",
            "Nature & Science","Feelings & Emotions","Health & Senses"]
    if o.get("category") not in CATS:
        row["issues"].append(f"CATEGORY_BAD:{o.get('category')!r}")

    # senses rules
    senses = o.get("senses") or []
    row["n_senses"] = len(senses)
    if len(senses) == 0:
        row["issues"].append("NO_SENSES")
    snos = [s.get("sense_no") for s in senses]
    if snos != list(range(1, len(senses)+1)):
        row["issues"].append(f"SENSE_NO_NONSEQ:{snos}")
    prims = [s for s in senses if s.get("is_primary") is True]
    if len(prims) != 1:
        row["issues"].append(f"PRIMARY_COUNT:{len(prims)}")

    # examples: exactly 3, each contains lemma as standalone token
    examples = o.get("examples") or []
    row["n_examples"] = len(examples)
    if len(examples) != 3:
        row["issues"].append(f"EXAMPLES_COUNT:{len(examples)}")
    lemma_words = tokenize_words(o.get("lemma", ""))
    for i, ex in enumerate(examples):
        et = (ex or {}).get("example_text", "")
        tw = tokenize_words(et)
        if not lemma_words or not lemma_words.issubset(tw):
            row["issues"].append(f"EXAMPLE_MISSING_LEMMA[{i}]:{et[:40]!r}")
        ice = (ex or {}).get("intended_cefr")
        if ice not in ["A1","A2","B1","B2","C1","C2"]:
            row["issues"].append(f"EXAMPLE_BAD_CEFR[{i}]:{ice!r}")

    # circular definition (contains lemma itself)
    lemma_l = (o.get("lemma") or "").lower()
    defn = (o.get("definition_en") or "").lower()
    if lemma_l and lemma_l in defn:
        row["issues"].append("DEFINITION_CONTAINS_LEMMA")
    tagline = [s.get("definition_en","").lower() for s in senses]
    for i, sd in enumerate(tagline):
        if lemma_l and lemma_l in sd:
            row["issues"].append(f"SENSE_DEF_CONTAINS_LEMMA[{i}]")

    # mnemonic null check
    row["mnemonic_entry"] = o.get("mnemonic_ar")
    row["mnemonic_is_null"] = o.get("mnemonic_ar") is None
    sense_mnemonics = [s.get("mnemonic_ar") for s in senses]
    row["mnemonic_sense_null_count"] = sum(1 for m in sense_mnemonics if m is None)
    if not row["mnemonic_is_null"]:
        mn = o.get("mnemonic_ar")
        if lemma_l and lemma_l in (mn or "").lower():
            row["issues"].append("MNEMONIC_CONTAINS_LEMMA")

    # relations bounds
    for fld, lo, hi in [("collocations",0,5),("synonyms",0,5),("antonyms",0,3)]:
        v = o.get(fld)
        if not isinstance(v, list) or not (lo <= len(v) <= hi):
            row["issues"].append(f"{fld.upper()}_BOUND:{len(v) if isinstance(v,list) else v!r}")
    rw = o.get("related_words") or {}
    if not isinstance(rw.get("en"), list) or not isinstance(rw.get("ar"), list):
        row["issues"].append("RELATED_WORDS_MISSING_EN_AR")

    # translations
    tr = o.get("translations") or {}
    arab = tr.get("arabic_ar")
    row["arabic_tr"] = arab
    if not arab or not arab.strip():
        row["issues"].append("ARABIC_TRANSLATION_EMPTY")

    # word_family
    wf = o.get("word_family") or {}
    for k in ["noun","verb","adj","adv"]:
        if k not in wf:
            row["issues"].append(f"WF_MISSING_{k}")

    # ai_confidence not scored but bounds check only (informational)
    row["ai_confidence"] = o.get("ai_confidence")

    rows.append(row)

# ---- Aggregate ----
print("=" * 70)
print("STRUCTURAL / SCHEMA COMPLIANCE (automated) — per word")
print("=" * 70)
for r in rows:
    tag = "PARSE_FAIL" if r.get("parse_err") else ("OK" if not r["issues"] else f"{len(r['issues'])}flags")
    print(f"\n[{r['wid']}] {r['word']} ({r['gold_pos_corr']}/{r['gold_cefr']}) senses={r.get('n_senses','?')} ex={r.get('n_examples','?')} mnem={r.get('mnemonic_is_null') is False and 'non-null' or 'NULL'} aiconf={r.get('ai_confidence')}")
    if r.get("parse_err"):
        print("   PARSE:", r["parse_err"])
    for iss in r["issues"]:
        print("   FLAG:", iss)

print("\n" + "=" * 70)
print("NULL BEHAVIOR METRICS")
print("=" * 70)
nn = [r for r in rows if r.get("mnemonic_is_null") is not None]
null_c = sum(1 for r in nn if r["mnemonic_is_null"])
print(f"mnemonic_ar NULL rate: {null_c}/{len(nn)} = {100*null_c/max(1,len(nn)):.0f}%")
print(f"mnemonic_ar non-null:  {len(nn)-null_c}/{len(nn)}")
sense_null = sum(r.get("mnemonic_sense_null_count",0) for r in nn)
sense_total = sum(r.get("n_senses",0) for r in nn)
print(f"sense-level mnemonic NULL: {sense_null}/{sense_total}")

print("\n" + "=" * 70)
print("CRITICAL AUTOMATED FLAGS SUMMARY")
print("=" * 70)
from collections import Counter
c = Counter()
for r in rows:
    for iss in r["issues"]:
        base = iss.split(":")[0].split("[")[0]
        c[base] += 1
for k, v in c.most_common():
    print(f"  {v:3d}  {k}")

# save machine-readable
out = [{"wid": r["wid"], "issues": r.get("issues", []), "parse_err": r.get("parse_err"),
        "mnemonic_is_null": r.get("mnemonic_is_null"), "n_senses": r.get("n_senses"),
        "ai_confidence": r.get("ai_confidence")} for r in rows]
with open(r"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\experiments\EXP-2026-09-03-001\output\auto_flags.json","w",encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("\nsaved auto_flags.json")
