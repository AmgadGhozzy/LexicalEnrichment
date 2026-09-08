"""Seed snapshot extractor for EXP-SEEDED-001 (BT-15 build).

Built from the frozen legacy source (WordsMaster.db) via pure
transport normalization ONLY — no semantic cleaning, no repair,
no filtering. Identity moves from the legacy columns to the
canonical (lemma, pos) key unchanged.

Governance:
- read-only DB access; never writes to WordsMaster.db.
- does NOT touch eval_identity_map.json; keying is by (lemma, pos)
  which is public in the blind package.
- rank / frequency / difficultyScore are EXCLUDED from the seed:
  legacy ranking heuristics must not re-pollute the generation.
- CEFR is carried as immutable identity metadata only; Gate A
  (EVP) still governs the canonical CEFR — the seed never makes a
  CEFR claim on its own.
"""

import hashlib
import json
import os
import sqlite3

SEED_FIELDS = (
    "definition_en", "explanation_ar", "usage_note",
    "phonetic_us", "phonetic_uk", "syllables",
    "synonyms", "antonyms", "collocations",
    "related_words", "word_family", "translations",
    "examples", "mnemonic", "semantic_tags",
)

# legacy column -> seed key
_COLUMN_MAP = {
    "definitionEn": "definition_en",
    "definitionAr": "explanation_ar",
    "usageNote": "usage_note",
    "phoneticUs": "phonetic_us",
    "phoneticUk": "phonetic_uk",
    "syllabify": "syllables",
    "synonyms": "synonyms",
    "antonyms": "antonyms",
    "collocations": "collocations",
    "relatedWords": "related_words",
    "wordFamily": "word_family",
    "arabicAr": "translations",
    "examples": "examples",
    "mnemonicAr": "mnemonic",
    "semanticTags": "semantic_tags",
}

# legacy metadata carried as read-only evidence (not LLM directives)
_META_MAP = {
    "category": "category",
    "primarySense": "primary_sense",
    "register": "register",
}


def _parse(value):
    """Transport decode: json, else raw string; None stays None."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        parsed = json.loads(value)
        return parsed
    except (ValueError, TypeError):
        return value


def row_to_seed(row, cefr):
    """Map a wordsMaster row (sqlite3.Row or dict) to a seed record.

    Pure transport: values decoded, keys renamed, order fixed.
    Nothing is filtered, cleaned, or reworded.
    """
    get = row.__getitem__
    seed = {"cefr": cefr}
    for col, key in _COLUMN_MAP.items():
        seed[key] = _parse(get(col))
    for col, key in _META_MAP.items():
        seed[key] = _parse(get(col))
    return seed


def build_seed_snapshot(db_path, identity_specs):
    """Map canonical (lemma, pos) identities to seed records.

    identity_specs: list of {'lemma':..,'pos':..,'cefr':..}.
    Returns (records, report). records keep the identity_spec
    fields verbatim plus the seed. report counts hits/misses.
    """
    con = sqlite3.connect("file:%s?mode=ro" % db_path,
                          uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    records = []
    report = {"total": len(identity_specs), "found": 0, "missing": []}
    for spec in identity_specs:
        lemma = spec["lemma"].strip().lower()
        pos = spec.get("pos")
        cur.execute(
            "SELECT * FROM wordsMaster "
            "WHERE lower(wordEn)=? AND lower(pos)=?",
            (lemma, (pos or "").lower()))
        rows = cur.fetchall()
        if len(rows) == 1:
            rec = dict(spec)
            rec["seed"] = row_to_seed(rows[0], spec.get("cefr"))
            records.append(rec)
            report["found"] += 1
        elif len(rows) > 1:
            report["missing"].append({"lemma": lemma, "pos": pos,
                                      "reason": "ambiguous"})
        else:
            report["missing"].append({"lemma": lemma, "pos": pos,
                                      "reason": "not found"})
    con.close()
    return records, report


def seed_sha256(records):
    blob = json.dumps(records, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def write_seed_snapshot(records, out_path):
    """Write jsonl + seed_snapshot_sha256 sidecar."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)),
                exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False, sort_keys=True)
             for r in records]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    digest = seed_sha256(records)
    with open(out_path + ".sha256", "w", encoding="utf-8") as f:
        f.write(digest + "\n")
    return digest