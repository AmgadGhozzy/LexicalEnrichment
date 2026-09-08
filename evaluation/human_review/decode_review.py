import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

base = r"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\human_review\reviews\HR-2026-09-03-001"
manifest = json.load(open(os.path.join(base, "manifest.json"), encoding="utf-8"))
resp = json.load(open(os.path.join(base, "responses.json"), encoding="utf-8"))["responses"]

by_id = {e["word_id"]: e for e in manifest["entries"]}

# Source-facing labels: which label (A/B) is exp, which is golden
def label_for(entry, src):
    return "A" if entry["a"] == src else "B"

rows = []
for r in resp:
    e = by_id[r["word_id"]]
    lab_exp = label_for(e, "exp")      # EXP-002 / v2.2.1
    lab_gold = label_for(e, "golden")  # GOLDEN
    def win(value):
        if value == lab_exp: return "EXP-002"
        if value == lab_gold: return "GOLDEN"
        return value  # TIE / N/A
    row = {
        "word": r["lemma"], "id": r["word_id"],
        "examples_win": win(r["examples"]),
        "mnemonic_win": win(r["mnemonic"]),
        "critical_error_entries": [
            "EXP-002" if r["critical_error"].get(lab_exp) else None,
            "GOLDEN" if r["critical_error"].get(lab_gold) else None,
        ],
        "meaningful": r["difference_meaningful"] == "yes",
        "notes": r["notes"],
        # raw
        "lab_exp": lab_exp, "lab_gold": lab_gold,
        "crit_A": r["critical_error"].get("A"), "crit_B": r["critical_error"].get("B"),
    }
    rows.append(row)

# ---- print per-word table ----
print("=" * 92)
print("HUMAN ADJUDICATION (4-word diagnostic sample)  [decoded from blind]")
print("=" * 92)
hdr = f"{'word':12} {'examples':10} {'mnemonic':10} {'crit error':14} {'meaningful':10}"
print(hdr)
print("-" * 92)
for r in rows:
    ce = ", ".join([c for c in r["critical_error_entries"] if c]) or "Neither"
    print(f"{r['word']:12} {r['examples_win']:10} {r['mnemonic_win']:10} {ce:14} {str(r['meaningful']):10}")

# ---- aggregate counts ----
n = len(rows)
def count(field):
    exp = sum(1 for r in rows if r[field] == "EXP-002")
    gold = sum(1 for r in rows if r[field] == "GOLDEN")
    tie = sum(1 for r in rows if r[field] == "TIE")
    na = sum(1 for r in rows if r[field] == "N/A")
    return exp, gold, tie, na

print("\n--- Aggregate win rates ---")
for f in ["examples_win", "mnemonic_win"]:
    exp, gold, tie, na = count(f)
    print(f"  {f:14} EXP-002 {exp} | GOLDEN {gold} | TIE {tie} | N/A {na}")

crit_exp = sum(1 for r in rows for c in r["critical_error_entries"] if c == "EXP-002")
crit_gold = sum(1 for r in rows for c in r["critical_error_entries"] if c == "GOLDEN")
print(f"  critical_error EXP-002={crit_exp} GOLDEN={crit_gold}")
meaningful_yes = sum(1 for r in rows if r["meaningful"])
print(f"  meaningful_difference=yes {meaningful_yes}/{n}")

print("\n--- Notes ---")
for r in rows:
    print(f"\n[{r['word']}]")
    print("   " + r["notes"].replace("\n", "\n   "))
