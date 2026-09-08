import sys, io, json, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from google.cloud import storage

exp = "EXP-2026-09-03-002"
b = storage.Client(project="gen-lang-client-0841388254").bucket("lexical-enrichment")
preds = [x for x in b.list_blobs(prefix=f"experiments/{exp}/output/") if x.name.endswith("predictions.jsonl")]
print("prediction blobs:", [x.name for x in preds])
local = rf"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\experiments\{exp}\output\predictions.jsonl"
os.makedirs(os.path.dirname(local), exist_ok=True)
preds[0].download_to_filename(local)
print("downloaded:", len(open(local, encoding="utf-8").readlines()), "records\n")

def strip_fences(t):
    m = re.search(r"\{.*\}", t, re.S)
    return m.group(0) if m else t.strip()

allobj = {}
ok = fail = parsefail = 0
for l in open(local, encoding="utf-8"):
    if not l.strip():
        continue
    rec = json.loads(l)
    key = rec.get("key", "")
    m = re.search(r"CAND-(\d+)$", key)
    if not m:
        continue
    wid = m.group(1)
    status = rec.get("status")
    cands = (rec.get("response") or {}).get("candidates", [])
    if status or not cands:
        print(f"{wid}: NO CAND status={status!r}")
        fail += 1
        continue
    c0 = cands[0]
    text = "".join(p.get("text", "") for p in (c0.get("content", {}) or {}).get("parts", []) if p.get("text"))
    try:
        obj = json.loads(strip_fences(text))
        allobj[wid] = obj
        ok += 1
    except Exception as e:
        print(f"{wid}: PARSE FAIL {str(e)[:100]}")
        parsefail += 1

print(f"TOTAL ok={ok} fail={fail} parsefail={parsefail}\n")

print("=" * 80)
print(f"MNEMONIC NULL AUDIT — {exp} (Prompt v2.2.1 balanced policy)")
print("=" * 80)
mn_entry_null = 0
sense_null = 0
sense_total = 0
for wid in sorted(allobj.keys(), key=int):
    o = allobj[wid]
    en = o.get("mnemonic_ar")
    senses = o.get("senses") or []
    sn = sum(1 for s in senses if s.get("mnemonic_ar") is None)
    sense_null += sn
    sense_total += len(senses)
    if en is None:
        mn_entry_null += 1
    print(f"[{wid}] mnem_entry_null={en is None} sense_mnem_null={sn}/{len(senses)}  entry={json.dumps(en,ensure_ascii=False)}")

print(f"\nmnemonic_ar entry NULL: {mn_entry_null}/{len(allobj)} = {100.0*mn_entry_null/max(1,len(allobj)):.0f}%")
print(f"mnemonic_ar sense NULL: {sense_null}/{sense_total} = {100.0*sense_null/max(1,sense_total):.0f}%")

with open(rf"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\experiments\{exp}\output\all_records.json", "w", encoding="utf-8") as f:
    json.dump(allobj, f, ensure_ascii=False, indent=2)
print("\nsaved all_records.json")
