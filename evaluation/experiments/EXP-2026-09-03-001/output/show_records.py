import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PRED = r"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\experiments\EXP-2026-09-03-001\output\predictions.jsonl"
GOLD = r"C:\Users\HP\Desktop\LexicalEnrichment\golden_set\golden_v2.json"

def load_preds(path):
    out = {}
    for l in open(path, encoding="utf-8"):
        if not l.strip():
            continue
        rec = json.loads(l)
        m = re.search(r"CAND-(\d+)$", rec.get("key", ""))
        if not m:
            continue
        resp = rec.get("response") or {}
        cands = resp.get("candidates") or []
        text = "".join(p.get("text","") for p in (cands[0].get("content") or {}).get("parts",[]) if p.get("text")) if cands else ""
        fm = re.search(r"\{.*\}", text, re.S)
        out[m.group(1)] = json.loads(fm.group(0)) if fm else None
    return out

def load_gold(path):
    return {str(e["id"]): e for e in json.load(open(path, encoding="utf-8"))}

preds = load_preds(PRED)
gold = load_gold(GOLD)

def jdump(x):
    return json.dumps(x, ensure_ascii=False)

wanted = sys.argv[1:] if len(sys.argv) > 1 else []
for wid in sorted(preds.keys(), key=int):
    if wanted and wid not in wanted:
        continue
    o = preds[wid]
    g = gold[wid]
    print("=" * 75)
    print(f"=== {wid} :: {g.get('wordEn')}  (gold POS orig={g.get('pos')} | cefr={g.get('cefrLevel')}) ===")
    print(f"  gold definition: {g.get('definitionEn')}")
    print(f"  NEW definition : {jdump(o.get('definition_en'))}")
    print(f"  gold def Ar    : {g.get('definitionAr')}")
    print(f"  NEW explain Ar : {jdump(o.get('explanation_ar'))}")
    print(f"  gold arabicTr  : {g.get('arabicAr')}")
    print(f"  NEW arabicTr   : {jdump((o.get('translations') or {}).get('arabic_ar'))}")
    print(f"  gold mnemonic  : {jdump(g.get('mnemonicAr'))}")
    print(f"  NEW mnemonic   : {jdump(o.get('mnemonic_ar'))}")
    print(f"  gold phonetic  : US={g.get('phoneticUs')} UK={g.get('phoneticUk')} AR={g.get('phoneticAr')}")
    print(f"  NEW phonetic   : US={jdump(o.get('phonetic_us'))} UK={jdump(o.get('phonetic_uk'))} AR={jdump(o.get('phonetic_ar'))}")
    print(f"  gold wordFamily: {g.get('wordFamily')}")
    print(f"  NEW wordFamily : {jdump(o.get('word_family'))}")
    print("  --- NEW senses ---")
    for s in o.get("senses") or []:
        print(f"     [{s.get('sense_no')}] primary={s.get('is_primary')} tag={s.get('semantic_tags')}")
        print(f"         def_en: {jdump(s.get('definition_en'))}")
        print(f"         short : {jdump(s.get('short_def_en'))}")
        print(f"         def_ar: {jdump(s.get('definition_ar'))}")
        print(f"         mnem  : {jdump(s.get('mnemonic_ar'))}")
        print(f"         note  : {jdump(s.get('usage_note'))}")
    print("  --- NEW examples ---")
    for ex in o.get("examples") or []:
        print(f"     ({ex.get('intended_cefr')}) {jdump(ex.get('example_text'))}")
    print(f"  gold colloc : {g.get('collocations')}")
    print(f"  NEW colloc  : {jdump(o.get('collocations'))}")
    print(f"  gold syn    : {g.get('synonyms')}")
    print(f"  NEW syn     : {jdump(o.get('synonyms'))}")
    print(f"  gold ant    : {g.get('antonyms')}")
    print(f"  NEW ant     : {jdump(o.get('antonyms'))}")
    print(f"  gold related: {g.get('relatedWords')}")
    print(f"  NEW related : {jdump(o.get('related_words'))}")
    print()
