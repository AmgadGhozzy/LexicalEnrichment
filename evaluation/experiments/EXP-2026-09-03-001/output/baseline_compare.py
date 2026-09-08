import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PRED = r"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\experiments\EXP-2026-09-03-001\output\predictions.jsonl"
GOLD = r"C:\Users\HP\Desktop\LexicalEnrichment\golden_set\golden_v2.json"
POS_CORR = {"474": "verb", "1071": "noun", "2532": "adj", "5167": "verb", "5433": "verb", "5496": "verb"}

def load_preds(path):
    out = {}
    for l in open(path, encoding="utf-8"):
        if not l.strip(): continue
        rec = json.loads(l)
        m = re.search(r"CAND-(\d+)$", rec.get("key",""))
        if not m: continue
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

def parsed_examples(g):
    try:
        return json.loads(g.get("examples") or "{}")
    except Exception:
        return {}
def parsed_arr(x):
    try: return json.loads(x) if x else []
    except Exception: return []

W = []
for wid in sorted(preds.keys(), key=int):
    o = preds[wid]
    g = gold[wid]
    gex = parsed_examples(g)
    new_ex = o.get("examples") or []
    gold_mnem = g.get("mnemonicAr")
    new_mnem = o.get("mnemonic_ar")
    W.append({
        "wid": wid, "word": g["wordEn"],
        "gold_pos_orig": g.get("pos"), "gold_pos_corr": POS_CORR.get(wid, g.get("pos")),
        "gold_has_mnem": bool(gold_mnem), "new_has_mnem": new_mnem is not None,
        "gold_n_examples": len([k for k in gex if gex.get(k)]),
        "new_n_examples": len(new_ex),
        "new_n_senses": len(o.get("senses") or []),
        "gold_phonetic_uk": g.get("phoneticUk"),
        "new_phonetic_uk": o.get("phonetic_uk"),
        "new_defn": o.get("definition_en"),
        "gold_defn": g.get("definitionEn"),
        "new_arabic": (o.get("translations") or {}).get("arabic_ar"),
        "gold_arabic": g.get("arabicAr"),
    })

print("="*140)
hdr = f"{'id':>4} {'word':12} {'gPOS':5} {'cPOS':5} {'gmnem':5} {'nmnem':5} {'gNex':4} {'nNex':4} {'nSense':5} {'gUK':12} {'nUK':12}"
print(hdr)
print("-"*140)
for w in W:
    print(f"{w['wid']:>4} {w['word']:12} {w['gold_pos_orig']:5} {w['gold_pos_corr']:5} "
          f"{str(w['gold_has_mnem']):5} {str(w['new_has_mnem']):5} {w['gold_n_examples']:<4} {w['new_n_examples']:<4} {w['new_n_senses']:<5} "
          f"{str(w['gold_phonetic_uk'] is not None):12} {str(w['new_phonetic_uk'] is not None):12}")

# Summary stats
n_mnem_gap = sum(1 for w in W if w["gold_has_mnem"] and not w["new_has_mnem"])
n_full = len(W)
print("\n--- mnemonic disappearance (golden HAS mnemonic, NEW null) ---")
print(f"  {n_mnem_gap}/{n_full} words that GOLDEN carries a mnemonic => NEW returned null")
for w in W:
    if w["gold_has_mnem"] and not w["new_has_mnem"]:
        print(f"    {w['wid']} {w['word']}:  golden='{gold.get(w['wid'],{}).get('mnemonicAr')}'")
print("\n--- senses split (NEW sense count vs golden single primarySense) ---")
for w in W:
    print(f"    {w['wid']} {w['word']}: NEW {w['new_n_senses']} sense(s); golden primarySense='{gold[w['wid']].get('primarySense')}'")
