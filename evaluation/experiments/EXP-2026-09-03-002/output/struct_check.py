import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PRED = r"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\experiments\EXP-2026-09-03-002\output\all_records.json"
GOLD = r"C:\Users\HP\Desktop\LexicalEnrichment\golden_set\golden_v2.json"
POS_CORR = {"474": "verb", "1071": "noun", "2532": "adj", "5167": "verb", "5433": "verb", "5496": "verb"}

allobj = json.load(open(PRED, encoding="utf-8"))
gold = {str(e["id"]): e for e in json.load(open(GOLD, encoding="utf-8"))}

def norm_pos(p): return (p or "").strip().lower()
def toks(s): return set(re.findall(r"[A-Za-z]+", s.lower()))

from collections import Counter
issues = Counter()
for wid in sorted(allobj.keys(), key=int):
    o = allobj[wid]
    g = gold[wid]
    if str(o.get("id")) != wid:
        issues["ID_MISMATCH"] += 1
    if norm_pos(o.get("pos")) != norm_pos(POS_CORR.get(wid, g.get("pos"))):
        issues["POS_MISMATCH"] += 1
    if (o.get("cefr_level") or "").upper() != (g.get("cefrLevel") or "").upper():
        issues["CEFR_MISMATCH"] += 1
    senses = o.get("senses") or []
    if [s.get("sense_no") for s in senses] != list(range(1, len(senses)+1)):
        issues["SENSE_NO_NONSEQ"] += 1
    prims = [s for s in senses if s.get("is_primary") is True]
    if len(prims) != 1:
        issues["PRIMARY_COUNT"] += 1
    exs = o.get("examples") or []
    if len(exs) != 3:
        issues["EXAMPLES_COUNT"] += 1
    lemma_t = toks(o.get("lemma",""))
    for i, ex in enumerate(exs):
        et = (ex or {}).get("example_text","")
        if not lemma_t or not lemma_t.issubset(toks(et)):
            issues[f"EXAMPLE_MISSING_LEMMA"] += 1
    dl = (o.get("definition_en") or "").lower()
    if (o.get("lemma") or "").lower() and (o.get("lemma") or "").lower() in dl:
        issues["DEFINITION_CONTAINS_LEMMA"] += 1
    for i, s in enumerate(senses):
        if (o.get("lemma") or "").lower() and (o.get("lemma") or "").lower() in (s.get("definition_en") or "").lower():
            issues["SENSE_DEF_CONTAINS_LEMMA"] += 1
    if not (o.get("mnemonic_ar") is None) and (o.get("lemma") or "").lower() and (o.get("lemma") or "").lower() in (o.get("mnemonic_ar") or "").lower():
        pass  # mnemonic may cite the lemma in Arabic text; not necessarily circular
    if not isinstance(o.get("collocations"), list) or not (0 <= len(o.get("collocations")) <= 5):
        issues["COLLOC_BOUND"] += 1
    if not isinstance(o.get("synonyms"), list) or not (0 <= len(o.get("synonyms")) <= 5):
        issues["SYN_BOUND"] += 1
    if not isinstance(o.get("antonyms"), list) or not (0 <= len(o.get("antonyms")) <= 3):
        issues["ANT_BOUND"] += 1
    tr = o.get("translations") or {}
    if not tr.get("arabic_ar"):
        issues["ARABIC_TR_EMPTY"] += 1

print("EXP-2026-09-03-002 STRUCTURAL FLAGS (m1 run)")
print("=" * 60)
if not issues:
    print("No structural flags across all 15 records.")
for k, v in issues.most_common():
    print(f"  {v:3d}  {k}")
