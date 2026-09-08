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

def jdump(x): return json.dumps(x, ensure_ascii=False)

NUL_TR = ["french_fr","german_de","spanish_es","chinese_zh","russian_ru","portuguese_pt","japanese_ja","italian_it","turkish_tr"]

print("="*80)
print("NULL-POLICY AUDIT — every nullable field, per word")
print("="*80)
tr_null = 0
tr_total = 0
mn_null = 0
for wid in sorted(preds.keys(), key=int):
    o = preds[wid]
    if not o:
        print(f"[{wid}] NO PARSE"); continue
    tr = o.get("translations") or {}
    trn = sum(1 for k in NUL_TR if tr.get(k) is None)
    trt = sum(1 for k in NUL_TR if k in tr)
    tr_null += trn; tr_total += trt
    mn = o.get("mnemonic_ar") is None
    mn_null += mn
    sense_n = o.get("senses") or []
    sense_mn = sum(1 for s in sense_n if s.get("mnemonic_ar") is None)
    print(f"[{wid}] {gold[wid]['wordEn']:12} mnem_entry_null={mn} sense_mnem_null={sense_mn}/{len(sense_n)} transl_null={trn}/{trt} phonetic_uk_null={(o.get('phonetic_uk') is None)}")

print(f"\nTRANSLATION field NULL rate: {tr_null}/{tr_total} = {100.0*tr_null/max(1,tr_total):.0f}%  (non-arabic, all nullable)")
print(f"MNEMONIC entry NULL rate:   {mn_null}/{len(preds)}")
n = sum(len((o.get('senses') or [])) for o in preds.values() if o)
nm = sum(sum(1 for s in (o.get('senses') or []) if s.get('mnemonic_ar') is None) for o in preds.values() if o)
print(f"MNEMONIC sense NULL rate:   {nm}/{n} = {100.0*nm/max(1,n):.0f}%")

# Non-null mnemonic inventory
print("\n" + "="*80)
print("NON-NULL MNEMONIC INVENTORY (entry-level)")
print("="*80)
for wid in sorted(preds.keys(), key=int):
    o = preds[wid]
    if o and o.get("mnemonic_ar") is not None:
        print(f"[{wid}] {gold[wid]['wordEn']}: {jdump(o.get('mnemonic_ar'))}")
# Any non-null sense mnemonics?
print("\nAny sense-level non-null mnemonics?")
any_sense = False
for wid in sorted(preds.keys(), key=int):
    o = preds[wid]
    if not o: continue
    for s in o.get("senses") or []:
        if s.get("mnemonic_ar") is not None:
            any_sense = True
            print(f"  [{wid}] sense {s.get('sense_no')}: {jdump(s.get('mnemonic_ar'))}")
if not any_sense:
    print("  NONE — all 26 senses have mnemonic_ar = null")

# Save null audit
with open(r"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\experiments\EXP-2026-09-03-001\output\null_audit.json","w",encoding="utf-8") as f:
    json.dump({
        "mnemonic_entry_null": mn_null, "mnemonic_entry_total": len(preds),
        "mnemonic_sense_null": nm, "mnemonic_sense_total": n,
        "translation_null": tr_null, "translation_total": tr_total,
    }, f, ensure_ascii=False, indent=2)
print("\nsaved null_audit.json")
