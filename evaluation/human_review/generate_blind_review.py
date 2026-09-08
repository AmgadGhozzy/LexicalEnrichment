"""
generate_blind_review.py
=======================
Generate a self-contained, blind human-review HTML artifact for lexical entries,
comparing two candidate payloads (e.g. golden_v2 baseline vs an experiment run)
WITHOUT revealing which candidate came from which source.

Separation of concerns (blindness is strict):
  - review.html         : NO source identifiers anywhere (values, attributes,
                          comments, or data-*). Only Option A / Option B content.
  - manifest.json       : the ONLY place holding the identity map (word_id -> which
                          candidate was A vs B). The reviewer must NOT receive this file.
  - responses.json      : reviewer's field-level judgments, saved/exported from the page
                          and later decoded against the manifest.

Usage
-----
  python generate_blind_review.py \
      --words election independent puzzle gastric \
      --seed 20260903 \
      --review-id HR-2026-09-03-001

  # to generate a subset from a words file later (each line a lemma), e.g. 100-word subset:
  python generate_blind_review.py --words-file words.txt --seed 20260903 --review-id HR-XXX

Outputs
-------
  evaluation/human_review/reviews/<review_id>/
      review.html       (blind artifact, reviewer opens this)
      manifest.json     (identity map, kept away from reviewer)
      responses.json    (empty skeleton, reviewer fills via the page)

Focus / criteria shown to reviewers are configurable via --fields (default all):
  --fields examples mnemonic defin arabic senses collo relations translation
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
TEMPLATE = os.path.join(HUMAN_DIR, "review_template.html")

# Source data paths (edit if sources move)
EXP_002_RECORDS = os.path.join(ROOT, "experiments", "EXP-2026-09-03-002", "output", "all_records.json")
GOLDEN = os.path.join(ROOT, "..", "golden_set", "golden_v2.json")

# Lemma -> id map for the 4 contested words (kept in sync with the manifest once chosen).
# The generator locates entries by lemma and keeps the numeric id into the manifest.


def _load_source(path, key="id"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # list -> dict by key
    if isinstance(data, list):
        return {str(row[key]): row for row in data}, data
    # maybe already a dict
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


def _single(d):
    return d if isinstance(d, list) else [d]


def build_candidate(source_name, rec):
    """Return a schema-neutral, normalized display DTO.

    Both sources are normalized to the SAME structure:
        {definition, arabic, primary, additional, examples:[{text}], mnemonic}
    so the HTML renderer is identical for every option (no shape/channel leaks:
    no senses-array asymmetry, no CEFR labels, no source-specific ordering).
    """
    opt = {"definition": None, "arabic": None,
           "primary": None, "additional": [],
           "examples": [], "mnemonic": None}
    if source_name == "exp":
        opt["definition"] = rec.get("definition_en")
        opt["arabic"] = rec.get("explanation_ar")
        senses = _single(rec.get("senses")) or []
        if senses:
            opt["primary"] = senses[0].get("definition_en")
            for s in senses[1:]:
                opt["additional"].append(s.get("definition_en"))
        opt["examples"] = [{"text": e.get("example_text")}
                           for e in (_parse_examples_str(rec.get("examples")))]
        opt["mnemonic"] = rec.get("mnemonic_ar") or None
    else:  # golden
        opt["definition"] = rec.get("definitionEn")
        opt["arabic"] = rec.get("definitionAr")
        opt["primary"] = rec.get("primarySense") or None
        opt["additional"] = []  # golden has no additional-senses array
        opt["examples"] = [{"text": e["text"]}
                           for e in (_parse_examples_str(rec.get("examples")))]
        opt["mnemonic"] = rec.get("mnemonicAr") or None
    return opt


def normalize_multispace(s):
    if s is None:
        return s
    return re.sub(r"[ \t]+", " ", str(s)).strip()


def main():
    ap = argparse.ArgumentParser(description="Generate a blind human-review HTML artifact.")
    ap.add_argument("--words", nargs="*", default=[], help="lemmas to include")
    ap.add_argument("--words-file", default=None, help="file with one lemma per line")
    ap.add_argument("--seed", type=int, required=True, help="deterministic randomization seed")
    ap.add_argument("--review-id", required=True, help="e.g. HR-2026-09-03-001")
    ap.add_argument("--fields", nargs="*", default=["examples", "mnemonic"],
                    help="judgment fields to present (only examples/mnemonic used here)")
    args = ap.parse_args()

    if args.words_file:
        with open(args.words_file, "r", encoding="utf-8") as f:
            lemmas = [ln.strip() for ln in f if ln.strip()]
    else:
        lemmas = args.words

    exp_recs, _ = _load_source(EXP_002_RECORDS)
    _, golden_list = _load_source(GOLDEN)
    golden_by_lemma = {}
    for row in golden_list:
        golden_by_lemma.setdefault(str(row.get("wordEn")).strip(), row)

    rng = random.Random(args.seed)

    # find entries
    entries = []
    missed = []
    for lemma in lemmas:
        gold = golden_by_lemma.get(lemma)
        if gold is None:
            missed.append(lemma)
            continue
        # find matching exp record by id
        exp = exp_recs.get(str(gold.get("id")))
        if exp is None:
            # try by lemma match
            for k, v in exp_recs.items():
                if str(v.get("lemma") or "").strip() == lemma:
                    exp = v
                    break
        if exp is None:
            missed.append(lemma + " (no exp match)")
            continue
        entries.append({"lemma": lemma, "word_id": gold.get("id"),
                        "pos": gold.get("pos"), "cefr": gold.get("cefrLevel"),
                        "exp": exp, "golden": gold})

    if missed:
        print("WARNING: not found:", missed)

    # blind card assembly (no identities pass through)
    cards = []  # display data
    manifest_entries = []  # identity map
    for e in entries:
        a_opts = build_candidate("exp", e["exp"])
        a_opts["label"] = "A"
        b_opts = build_candidate("golden", e["golden"])
        b_opts["label"] = "B"
        pair = [a_opts, b_opts]
        rng.shuffle(pair)
        display = {"lemma": e["lemma"], "word_id": e["word_id"],
                   "pos": e["pos"],
                   "options": pair}
        cards.append(display)
        # map which label maps to which source
        src_by_label = {}
        for opt in pair:
            src_by_label[opt["label"]] = "exp" if opt is a_opts else "golden"
        # example_count is recorded OUTSIDE the blind artifact (in the manifest)
        # for post-review analytics only; it is never shown to the reviewer.
        manifest_entries.append({"word_id": e["word_id"], "lemma": e["lemma"],
                                 "a": src_by_label.get("A"), "b": src_by_label.get("B"),
                                 "example_count": {src_by_label.get("A"): len(a_opts["examples"]),
                                                   src_by_label.get("B"): len(b_opts["examples"])}})

    # guard: ensure no source identifiers anywhere in display payload
    # Strong tokens that must NEVER appear (values, attrs, comments).
    # Weak substrings like 'exp'/'new'/'old' are intentionally excluded because
    # they collide with ordinary English/JS words and would false-positive.
    strong_forbid = ["golden", "v2.2", "v2.1", "v1.1", "EXP-", "baseline",
                     "experiment", "gcp", "vertex", "gemini", "EXP-002",
                     "EXP-001", "EXP-JUDGE"]
    # Whole-word provenance tokens that must never appear as standalone words
    # in the rendered HTML. NOTE: 'new'/'old'/'model' are deliberately excluded:
    # 'new'/'old' can legitimately occur inside English example sentences, and
    # 'model' can appear in pedagogical prose; they are not provenance signals.
    word_forbid = ["golden", "baseline", "prompt", "version", "experiment",
                   "generator", "manifest", "exp-002", "exp-001",
                   "v2.2.1", "v2.2.0", "source"]
    for label in ("A", "B"):
        for card in cards:
            for opt in card["options"]:
                if str(opt.get("label")) == label and label.lower() in strong_forbid:
                    raise SystemExit("BLINDNESS VIOLATION: identity used as a label")
    dump_low = json.dumps(cards).lower()
    leaks = [tok for tok in strong_forbid if tok in dump_low]
    if leaks:
        raise SystemExit(f"BLINDNESS VIOLATION: tokens leaked into card payload: {leaks}")
    print("Blindness sanity (payload): OK")

    review_dir = os.path.join(REVIEWS_DIR, args.review_id)
    os.makedirs(review_dir, exist_ok=True)

    # manifest (identity map) — kept separate, NOT to be given to the reviewer
    manifest = {"review_id": args.review_id, "seed": args.seed,
                "entries": manifest_entries}
    with open(os.path.join(review_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # review.html — inject the blind data
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        tpl = f.read()
    tpl = tpl.replace("__WORDS_JSON__", json.dumps(cards, ensure_ascii=False))
    tpl = tpl.replace("__REVIEW_ID__", args.review_id)
    tpl = tpl.replace("__REVIEW_TITLE__", args.review_id)
    with open(os.path.join(review_dir, "review.html"), "w", encoding="utf-8") as f:
        f.write(tpl)

    # Final blindness audit against the rendered HTML (values, attrs, comments).
    html_low = tpl.lower()
    html_leaks = [tok for tok in strong_forbid if tok in html_low]
    if html_leaks:
        raise SystemExit(f"BLINDNESS VIOLATION in rendered review.html: {html_leaks}")
    # whole-word provenance tokens (word-boundary) in the rendered HTML
    wb_leaks = [tok for tok in word_forbid
                if re.search(r"(?<![a-z0-9-])" + re.escape(tok) + r"(?![a-z0-9-])", html_low)]
    if wb_leaks:
        raise SystemExit(f"BLINDNESS VIOLATION (whole-word) in rendered review.html: {wb_leaks}")
    print("Blindness sanity (rendered review.html): OK")

    # responses skeleton
    skeleton = {"review_id": args.review_id,
                "responses": [{"word_id": c["word_id"], "lemma": c["lemma"],
                               "examples": None, "mnemonic": None,
                               "critical_error": {"A": False, "B": False},
                               "difference_meaningful": None, "notes": ""}
                              for c in cards]}
    with open(os.path.join(review_dir, "responses.json"), "w", encoding="utf-8") as f:
        json.dump(skeleton, f, ensure_ascii=False, indent=2)

    print("Wrote review.html, manifest.json, responses.json ->", review_dir)
    print("Reviewer opens: review.html   (manifest.json must stay private)")


if __name__ == "__main__":
    main()
