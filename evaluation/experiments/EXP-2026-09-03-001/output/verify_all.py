import sys, io, json, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from google.cloud import storage

exp = "EXP-2026-09-03-001"
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

records = []
for l in open(local, encoding="utf-8"):
    if not l.strip():
        continue
    rec = json.loads(l)
    records.append(rec)

ok = fail = parsefail = 0
for rec in sorted(records, key=lambda r: r.get("key", "")):
    key = rec.get("key")
    status = rec.get("status")
    cands = (rec.get("response") or {}).get("candidates", [])
    if status or not cands:
        print(f"{key}: NO CANDIDATES status={status!r}")
        fail += 1
        continue
    c0 = cands[0]
    text = "".join(p.get("text", "") for p in (c0.get("content", {}) or {}).get("parts", []) if p.get("text"))
    try:
        obj = json.loads(strip_fences(text))
    except Exception as e:
        print(f"{key}: PARSE FAIL status={status!r} err={str(e)[:100]}")
        parsefail += 1
        continue
    ok += 1
    print(f"{key}: id={obj.get('id')} lemma={obj.get('lemma')!r:18} pos={obj.get('pos')!r:6} cefr={obj.get('cefr_level')} finish={c0.get('finishReason')} fields={len(obj)}")

print(f"\nTOTAL={len(records)} OK={ok} NO_CAND={fail} PARSE_FAIL={parsefail}")
