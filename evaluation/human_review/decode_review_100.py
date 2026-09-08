"""Decode blind judgments for the 100-pilot human review against its manifest.

Usage:
  python decode_review_100.py [reviews/HR-2026-09-03-100]

Reads manifest.json (private identity map) + responses.json (filled judgments)
and prints a per-word table plus aggregate win rates, null-verdict counts,
critical-error counts, and notes. Never ships the identity map to reviewers.
"""
import sys
import io
import json
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

base = (sys.argv[1] if len(sys.argv) > 1
        else r"C:\Users\HP\Desktop\LexicalEnrichment\evaluation\human_review\reviews\HR-2026-09-03-100")
manifest = json.load(open(os.path.join(base, "manifest.json"), encoding="utf-8"))
resp = json.load(open(os.path.join(base, "responses.json"), encoding="utf-8"))["responses"]
EXP = manifest.get("exp_label", "EXP")

by_id = {e["word_id"]: e for e in manifest["entries"]}


def label_for(entry, src):
    return "A" if entry["a"] == src else "B"


FIELDS = ["definition", "arabic", "senses", "examples",
          "translations", "relations", "mnemonic"]

rows = []
for r in resp:
    e = by_id[r["word_id"]]
    lab_exp = label_for(e, "exp")
    lab_gold = label_for(e, "golden")

    def win(value):
        if value == lab_exp:
            return EXP
        if value == lab_gold:
            return "GOLDEN"
        return value  # TIE / N/A / None

    row = {"word": r["lemma"], "id": r["word_id"],
           "lab_exp": lab_exp, "lab_gold": lab_gold,
           "meaningful": (str(r.get("difference_meaningful") or "").lower() == "yes"
                          or r.get("difference_meaningful") is True),
           "null_verdict": r.get("null_verdict"),
           "notes": r.get("notes") or ""}
    for f in FIELDS:
        row[f] = win(r.get(f))
    ce = r.get("critical_error") or {}
    row["crit_exp"] = bool(ce.get(lab_exp))
    row["crit_gold"] = bool(ce.get(lab_gold))
    rows.append(row)

print("=" * 120)
print("HUMAN ADJUDICATION (100-pilot, 12-word sample)  [decoded from blind]  exp=%s" % EXP)
print("=" * 120)
hdr = "%-15s %-7s %-7s %-7s %-7s %-7s %-7s %-7s %-10s %-8s" % (
    "word", "defin", "arabic", "senses", "exmpl", "trans", "relat", "mnem",
    "null", "meaning")
print(hdr)
print("-" * 120)
for r in rows:
    ce = ",".join([s for s, f in ((EXP, r["crit_exp"]), ("GOLDEN", r["crit_gold"])) if f]) or "-"
    print("%-15s %-7s %-7s %-7s %-7s %-7s %-7s %-7s %-10s %-8s  crit:%s" % (
        r["word"], str(r["definition"]), str(r["arabic"]), str(r["senses"]),
        str(r["examples"]), str(r["translations"]), str(r["relations"]),
        str(r["mnemonic"]), str(r["null_verdict"]), str(r["meaningful"]), ce))

n = len(rows)
print("\n--- Aggregate win rates (n=%d) ---" % n)
for f in FIELDS:
    exp = sum(1 for r in rows if r[f] == EXP)
    gold = sum(1 for r in rows if r[f] == "GOLDEN")
    tie = sum(1 for r in rows if r[f] == "TIE")
    na = sum(1 for r in rows if r[f] in ("N/A", None))
    print("  %-12s %s %d | GOLDEN %d | TIE %d | N/A %d" % (f, EXP, exp, gold, tie, na))

from collections import Counter
print("  null_verdict:", dict(Counter(str(r["null_verdict"]) for r in rows)))
print("  critical_error %s=%d GOLDEN=%d" % (
    EXP, sum(1 for r in rows if r["crit_exp"]),
    sum(1 for r in rows if r["crit_gold"])))
print("  meaningful_difference=yes %d/%d" % (sum(1 for r in rows if r["meaningful"]), n))

print("\n--- Null instances in this sample (from manifest, private) ---")
for r in rows:
    e = by_id[r["id"]]
    mn = e.get("mnemonic_null") or {}
    nulls = [lab for lab, isnull in mn.items() if isnull]
    if nulls:
        print("  %-15s mnemonic null on label(s) %s | reviewer verdict: %s" % (
            r["word"], ",".join(nulls), r["null_verdict"]))

print("\n--- Notes ---")
for r in rows:
    if (r["notes"] or "").strip():
        print("\n[%s]" % r["word"])
        print("   " + r["notes"].replace("\n", "\n   "))
