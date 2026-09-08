"""
generate_blind_review_100.py
============================
100-word-pilot blind review builder: golden_v2 baseline vs an experiment run
(e.g. EXP-2026-09-03-003), WITHOUT revealing which candidate came from which source.

Compared to generate_blind_review.py (4-word diagnostic):
  - word selection by numeric --word-ids ( unambiguous for polysemy pairs like
    trick verb/noun or dump verb/noun sharing one lemma);
  - configurable --exp-records (id-keyed all_records.json) and --exp-label
    (label text is PRIVATE: manifest/decode only, never rendered);
  - extended schema-neutral DTO: definition / arabic / senses / examples /
    translations / relations / mnemonic, rendered by review_template_100.html;
  - responses capture 9 criteria + null verdict (Correct/Incorrect/Borderline).

Separation of concerns (blindness is strict):
  - review.html   : NO source identifiers anywhere. Only Option A / Option B.
  - manifest.json : the ONLY place holding the identity map. Never to reviewer.
  - responses.json: reviewer's judgments, decoded against the manifest.

Usage
-----
  python generate_blind_review_100.py \
      --word-ids 3061 2016 937 6006 1289 6917 6077 4969 1217 5942 2902 4449 \
      --seed 20260903 \
      --review-id HR-2026-09-03-100
"""

import argparse
import io
import json
import os
import random
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../evaluation
HUMAN_DIR = os.path.join(ROOT, "human_review")
REVIEWS_DIR = os.path.join(HUMAN_DIR, "reviews")
TEMPLATE = os.path.join(HUMAN_DIR, "review_template_100.html")

DEFAULT_EXP_RECORDS = os.path.join(
    ROOT, "experiments", "EXP-2026-09-03-003", "output", "all_records.json")
GOLDEN = os.path.join(ROOT, "..", "golden_set", "golden_v2.json")


def _load_source(path, key="id"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {str(row[key]): row for row in data}, data
    if isinstance(data, dict):
        return data, list(data.values())
    raise TypeError("unhandled source structure")


def _parse_examples_str(raw):
    """golden stores examples as a JSON string {cefr: text,...}; exp stores a list."""
    if isinstance(raw, list):
        out = []
        for e in raw:
            if isinstance(e, dict):
                out.append({"text": e.get("example_text"), "cefr": e.get("intended_cefr")})
            else:
                out.append({"text": e, "cefr": None})
        return out
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
        except Exception:
            obj = {}
        return [{"text": v, "cefr": k} for k, v in obj.items() if v]
    return []


def _coerce(raw):
    """golden_v2 stores several relation fields as JSON-encoded STRINGS
    (e.g. synonyms='[\"phone\", ...]', relatedWords='{\"en\": [...]}'),
    while exp records use native lists/dicts. Normalize both to objects."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return raw
    return raw


def _join(items):
    items = _coerce(items)
    if isinstance(items, str):
        items = [items] if items.strip() else []
    items = [str(x).strip() for x in (items or []) if str(x).strip()]
    return ", ".join(items) if items else "(none)"


def _family_str(fam):
    fam = _coerce(fam)
    if not isinstance(fam, dict):
        return "(none)"
    parts = []
    for k in ("noun", "verb", "adj", "adv"):
        v = fam.get(k)
        if v:
            parts.append("%s=%s" % (k, v))
    return "; ".join(parts) if parts else "(none)"


def _relations_str(syn, ant, rel, collo, fam):
    rel = _coerce(rel)
    if isinstance(rel, dict):
        rel_en = _join(rel.get("en"))
        rel_ar = _join(rel.get("ar"))
    else:
        rel_en, rel_ar = "(none)", "(none)"
    return ("Synonyms: %s | Antonyms: %s | Related EN: %s | Related AR: %s | "
            "Collocations: %s | Family: %s" % (
                _join(syn), _join(ant), rel_en, rel_ar,
                _join(collo), _family_str(fam)))


def build_candidate(source_name, rec):
    """Schema-neutral normalized display DTO, identical shape for both sources."""
    opt = {"definition": None, "arabic": None, "senses": [],
           "examples": [], "translations": None, "relations": None,
           "mnemonic": None}
    if source_name == "exp":
        opt["definition"] = rec.get("definition_en")
        opt["arabic"] = rec.get("explanation_ar")
        for s in (rec.get("senses") or []):
            if isinstance(s, dict):
                en = (s.get("definition_en") or "").strip()
                ar = (s.get("definition_ar") or "").strip()
                opt["senses"].append(en + (" — " + ar if ar else ""))
            else:
                opt["senses"].append(str(s))
        opt["examples"] = [{"text": e.get("text")}
                           for e in _parse_examples_str(rec.get("examples"))]
        tr = rec.get("translations") or {}
        opt["translations"] = tr.get("arabic_ar") if isinstance(tr, dict) else None
        opt["relations"] = _relations_str(
            rec.get("synonyms"), rec.get("antonyms"),
            rec.get("related_words"), rec.get("collocations"),
            rec.get("word_family"))
        opt["mnemonic"] = rec.get("mnemonic_ar") or None
    else:  # golden
        opt["definition"] = rec.get("definitionEn")
        opt["arabic"] = rec.get("definitionAr")
        prim = (rec.get("primarySense") or "").strip()
        den = (rec.get("definitionEn") or "").strip()
        dar = (rec.get("definitionAr") or "").strip()
        opt["senses"] = [prim + (" — " + den if den else "")
                         + (" — " + dar if dar else "")]
        opt["examples"] = [{"text": e["text"]}
                           for e in _parse_examples_str(rec.get("examples"))]
        opt["translations"] = rec.get("arabicAr")
        opt["relations"] = _relations_str(
            rec.get("synonyms"), rec.get("antonyms"),
            rec.get("relatedWords"), rec.get("collocations"),
            rec.get("wordFamily"))
        opt["mnemonic"] = rec.get("mnemonicAr") or None
    return opt


def normalize_multispace(s):
    if s is None:
        return s
    return re.sub(r"[ \t]+", " ", str(s)).strip()


def main():
    ap = argparse.ArgumentParser(description="Generate a blind human-review HTML artifact (100-pilot).")
    ap.add_argument("--word-ids", nargs="*", type=int, default=[],
                    help="numeric golden_v2 ids to include (unambiguous)")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--review-id", required=True, help="e.g. HR-2026-09-03-100")
    ap.add_argument("--exp-records", default=DEFAULT_EXP_RECORDS,
                    help="id-keyed all_records.json for the experiment run")
    ap.add_argument("--exp-label", default="EXP-003",
                    help="private label for manifest/decode (never rendered)")
    args = ap.parse_args()

    exp_recs, _ = _load_source(args.exp_records)
    _, golden_list = _load_source(GOLDEN)
    golden_by_id = {}
    for row in golden_list:
        golden_by_id[str(row.get("id"))] = row

    rng = random.Random(args.seed)

    entries, missed = [], []
    for wid in args.word_ids:
        gold = golden_by_id.get(str(wid))
        exp = exp_recs.get(str(wid))
        if gold is None or exp is None:
            missed.append("%s%s" % (wid,
                                    "" if gold and exp else
                                    " (missing %s)" % "/".join(
                                        [n for n, v in (("golden", gold),
                                                        ("exp", exp)) if v is None])))
            continue
        entries.append({"lemma": gold.get("wordEn"), "word_id": gold.get("id"),
                        "pos": gold.get("pos"), "cefr": gold.get("cefrLevel"),
                        "exp": exp, "golden": gold})
    if missed:
        print("WARNING: not found:", missed)

    cards, manifest_entries = [], []
    pos_mismatch = []
    for e in entries:
        a_opts = build_candidate("exp", e["exp"])
        a_opts["label"] = "A"
        b_opts = build_candidate("golden", e["golden"])
        b_opts["label"] = "B"
        pair = [a_opts, b_opts]
        rng.shuffle(pair)
        display = {"lemma": e["lemma"], "word_id": e["word_id"],
                   "pos": e["pos"], "options": pair}
        cards.append(display)
        src_by_label = {}
        for opt in pair:
            src_by_label[opt["label"]] = "exp" if opt is a_opts else "golden"
        if str(e["exp"].get("pos") or "").strip().lower() != str(e["pos"] or "").strip().lower():
            pos_mismatch.append((e["word_id"], e["lemma"], e["pos"], e["exp"].get("pos")))
        manifest_entries.append({
            "word_id": e["word_id"], "lemma": e["lemma"],
            "pos_golden": e["pos"], "pos_exp": e["exp"].get("pos"),
            "cefr": e["cefr"],
            "a": src_by_label.get("A"), "b": src_by_label.get("B"),
            "example_count": {src_by_label.get("A"): len(a_opts["examples"]),
                              src_by_label.get("B"): len(b_opts["examples"])},
            "sense_count": {src_by_label.get("A"): len(a_opts["senses"]),
                            src_by_label.get("B"): len(b_opts["senses"])},
            "mnemonic_null": {src_by_label.get("A"): a_opts["mnemonic"] is None,
                              src_by_label.get("B"): b_opts["mnemonic"] is None},
        })
    if pos_mismatch:
        print("WARNING pos mismatch gold-vs-exp:", pos_mismatch)
    else:
        print("POS agreement gold-vs-exp: OK for all %d words" % len(entries))

    strong_forbid = ["golden", "v2.2", "v2.1", "v1.1", "EXP-", "baseline",
                     "experiment", "gcp", "vertex", "gemini", "EXP-002",
                     "EXP-001", "EXP-003", "EXP-JUDGE"]
    word_forbid = ["golden", "baseline", "prompt", "version", "experiment",
                   "generator", "manifest",
                   "v2.2.1", "v2.2.0", "source"]
    for label in ("A", "B"):
        for card in cards:
            for opt in card["options"]:
                if str(opt.get("label")) == label and label.lower() in strong_forbid:
                    raise SystemExit("BLINDNESS VIOLATION: identity used as a label")
    dump_low = json.dumps(cards).lower()
    leaks = [tok for tok in strong_forbid if tok in dump_low]
    if leaks:
        raise SystemExit("BLINDNESS VIOLATION: tokens leaked into card payload: %s" % leaks)
    print("Blindness sanity (payload): OK")

    review_dir = os.path.join(REVIEWS_DIR, args.review_id)
    os.makedirs(review_dir, exist_ok=True)

    manifest = {"review_id": args.review_id, "seed": args.seed,
                "exp_label": args.exp_label,
                "exp_records": os.path.basename(args.exp_records),
                "entries": manifest_entries}
    with open(os.path.join(review_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with open(TEMPLATE, "r", encoding="utf-8") as f:
        tpl = f.read()
    tpl = tpl.replace("__WORDS_JSON__", json.dumps(cards, ensure_ascii=False))
    tpl = tpl.replace("__REVIEW_ID__", args.review_id)
    tpl = tpl.replace("__REVIEW_TITLE__", args.review_id)
    with open(os.path.join(review_dir, "review.html"), "w", encoding="utf-8") as f:
        f.write(tpl)

    html_low = tpl.lower()
    html_leaks = [tok for tok in strong_forbid if tok in html_low]
    if html_leaks:
        raise SystemExit("BLINDNESS VIOLATION in rendered review.html: %s" % html_leaks)
    wb_leaks = [tok for tok in word_forbid
                if re.search(r"(?<![a-z0-9-])" + re.escape(tok) + r"(?![a-z0-9-])", html_low)]
    if wb_leaks:
        raise SystemExit("BLINDNESS VIOLATION (whole-word) in rendered review.html: %s" % wb_leaks)
    print("Blindness sanity (rendered review.html): OK")

    skeleton = {"review_id": args.review_id,
                "responses": [{"word_id": c["word_id"], "lemma": c["lemma"],
                               "definition": None, "arabic": None, "senses": None,
                               "examples": None, "translations": None,
                               "relations": None, "mnemonic": None,
                               "null_verdict": None,
                               "critical_error": {"A": False, "B": False},
                               "difference_meaningful": None, "notes": ""}
                              for c in cards]}
    with open(os.path.join(review_dir, "responses.json"), "w", encoding="utf-8") as f:
        json.dump(skeleton, f, ensure_ascii=False, indent=2)

    print("Wrote review.html, manifest.json, responses.json ->", review_dir)
    print("Reviewer opens: review.html   (manifest.json must stay private)")


if __name__ == "__main__":
    main()
