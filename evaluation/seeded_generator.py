"""Seeded generation runner for EXP-SEEDED-001 (Challenger arm).

Builds on the user-supplied verbatim prompt
(lexical_enrichment_seeded_v1.txt), deterministic field validation,
and the seed-preservation classifier. Field decisions (action +
reason) are captured as provenance AFTER generation via a separate
lightweight call, because the canonical prompt returns schema-only
JSON — the canonical candidate record never carries them.

Design locks:
- identity fields (lemma/pos/cefr) come from the seed record only.
- no rank / frequency / difficulty_score ever enters an LLM prompt.
- candidates are validated deterministically (seeded_validator);
  semantic quality is NOT assessed here (blind evaluator's job).
- quota events never become quality failures; pacing + 429 ladder +
  checkpoint resume mirror resume_356.py behavior.
"""

import json
import os
import random
import re
import sys
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.lexical_validator import (
    contains_target, is_circular_definition, GENERIC_NULL_VALUES)
from evaluation.seed_preservation import (
    FIELDS, classify_field, field_is_valid, seed_preservation_report)

DECISION_PROMPT = """You are an audit tool for a seeded dictionary regeneration.

Given the LEGACY value and the NEW CANDIDATE value for each field below,
declare what decision the candidate actually made per field. Declarations
are provenance, not verdicts: a declared reason never certifies quality.
Semantic better/worse is decided later by blind evaluation.

For every field output exactly these keys:
  "field": {{
    "action": "preserve" | "improve" | "replace" | "null",
    "reason": "one short concrete reason, or '' if kept as-is",
    "legacy_state": "null" | "non_null",
    "legacy_defect": true | false,
    "replacement_superiority": true | false,
    "evidence": "concrete evidence string, or ''"
  }}

Rules:
- legacy_state must match the LEGACY value shown ("null" only when the
  legacy value is genuinely absent or empty).
- action "null" on a non-null legacy REQUIRES legacy_defect=true AND a
  concrete evidence string naming the defect. Vague preferences such as
  "not ideal", "cannot improve", "prefer NULL", or "cleaner" are rejected.
- action "improve"/"replace" on a non-null legacy REQUIRES
  replacement_superiority=true plus a concrete reason. The declaration
  does not certify that the replacement is actually better.
- If a field was left identical, action must be "preserve" with
  legacy_defect=false, replacement_superiority=false, evidence "".

Return JSON only, with keys: {fields}. If a field was left identical,
action must be "preserve" with reason "".

LEGACY:
{legacy}

CANDIDATE:
{candidate}

Return JSON only. No markdown. No comments.
"""

PROMPT_CONTRACT_FIELDS = (
    "lemma", "pos", "cefr", "definition_en", "explanation_ar",
    "senses", "examples", "translations", "relations", "mnemonic",
    "phonetic_us", "phonetic_uk", "syllables", "semantic_tags",
    "ai_confidence",
)


def load_seed_snapshot(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def build_generation_prompt(identity, seed_blob, prompt_text):
    context = (
        "### SEEDED SOURCE (legacy reference, provided read-only)\n"
        + json.dumps(seed_blob, ensure_ascii=False, indent=2)
        + "\n\n### TARGET IDENTITY\nlemma: %s\npos: %s\ncefr: %s\n"
    ) % (identity["lemma"], identity.get("pos", ""), identity.get("cefr"))
    return ("%s\n\n%s\n\nProduce the contract-conforming candidate JSON "
            "for this identity now." % (prompt_text, context))


def parse_candidate(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _translations_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("arabic_ar", "ar", "Arabic"):
            if key in value and value[key]:
                return value[key]
        vals = [str(v) for v in value.values() if str(v).strip()]
        return vals[0] if vals else ""
    if isinstance(value, list):
        parts = []
        for v in value:
            if isinstance(v, dict):
                for key in ("text", "arabic_ar", "ar"):
                    if v.get(key):
                        parts.append(str(v[key]))
                        break
            elif str(v).strip():
                parts.append(str(v))
        return " ".join(parts)
    return str(value) if value else ""


def _relation_list(value):
    if value is None:
        return []
    if isinstance(value, dict):
        return []
    if isinstance(value, list):
        return value
    return [value] if value else []


def _relations_of(out):
    rels = out.get("relations") or {}
    if not isinstance(rels, dict):
        rels = {}
    return {
        "synonyms": _relation_list(rels.get("synonyms"))
                     or _relation_list(out.get("synonyms")),
        "antonyms": _relation_list(rels.get("antonyms"))
                     or _relation_list(out.get("antonyms")),
        "collocations": _relation_list(rels.get("collocations"))
                         or _relation_list(out.get("collocations")),
    }


def renormalize_candidate(out):
    """Map seeded output -> (classifier cursor, blind arm output)."""
    rels = _relations_of(out)
    mnemonic = out.get("mnemonic")
    if mnemonic is None:
        mnemonic = out.get("mnemonic_ar")
    translations = _translations_text(out.get("translations"))
    cursor = {
        "definition_en": out.get("definition_en"),
        "explanation_ar": out.get("explanation_ar"),
        "examples": out.get("examples") or [],
        "translations": translations,
        "synonyms": rels["synonyms"],
        "antonyms": rels["antonyms"],
        "collocations": rels["collocations"],
        "mnemonic": mnemonic,
    }
    arm = {
        "definition_en": out.get("definition_en"),
        "explanation_ar": out.get("explanation_ar"),
        "examples": out.get("examples") or [],
        "translations": {"arabic_ar": translations},
        "synonyms": rels["synonyms"],
        "antonyms": rels["antonyms"],
        "collocations": rels["collocations"],
        "mnemonic_ar": mnemonic,
    }
    return cursor, arm


def validate_seeded_candidate(out, identity, cursor):
    """Deterministic checks. Returns (checks, artifact_pass)."""
    checks = {}
    lemma = identity["lemma"]
    pos = identity.get("pos")

    for field in PROMPT_CONTRACT_FIELDS:
        if field not in out:
            checks[field] = {"status": "fail", "message": "missing"}
            continue
        if out[field] is None and field not in ("phonetic_uk", "mnemonic"):
            checks[field] = {"status": "fail", "message": "null_forbidden"}
            continue
        checks[field] = {"status": "pass"}

    def ok(name, passed, msg=""):
        checks[name] = {"status": "pass" if passed else "fail",
                        "message": msg if not passed else ""}

    ok("identity_lemma", str(out.get("lemma", "")).strip().lower()
       == lemma.strip().lower())
    ok("identity_pos", str(out.get("pos", "")).strip().lower()
       == str(pos or "").strip().lower())
    ok("identity_cefr", str(out.get("cefr", "")).strip().lower()
       == str(identity.get("cefr") or "").strip().lower())

    defn = cursor["definition_en"]
    ok("definition_nonempty", bool(defn and str(defn).strip()))
    if defn:
        ok("definition_not_circular",
           not is_circular_definition(str(defn), lemma))

    exp = cursor["explanation_ar"]
    norm = " ".join(str(exp).strip().lower().split()) if exp else ""
    ok("explanation_nonempty", bool(norm))
    ok("explanation_not_generic", bool(norm) and norm not in GENERIC_NULL_VALUES
       and not norm.startswith("[") and not norm.startswith("("))

    examples = cursor["examples"]
    texts = [e.get("example_text") if isinstance(e, dict) else e
             for e in examples]
    ok("examples_count", len(texts) == 3,
       f"expected 3, got {len(texts)}")
    ok("examples_all_nonempty",
       all(bool(t and str(t).strip()) for t in texts))
    ok("examples_contain_target",
       all(contains_target(str(t), lemma) for t in texts))

    ok("translations_nonempty", bool(cursor["translations"].strip()))
    total_rels = (cursor["synonyms"] + cursor["antonyms"]
                  + cursor["collocations"])
    ok("relations_some_content", bool(total_rels))

    mnem = cursor["mnemonic"]
    mnorm = " ".join(str(mnem).strip().lower().split()) if mnem else ""
    ok("mnemonic_null_or_useful",
       mnem is None or (bool(mnorm) and mnorm not in GENERIC_NULL_VALUES))

    ai_conf = out.get("ai_confidence")
    ok("ai_confidence_numeric", isinstance(ai_conf, (int, float)))

    artifact_pass = all(c["status"] == "pass"
                        for c in checks.values())
    return checks, artifact_pass


def source_type_for(category, action):
    """Provenance source_type mapping (forensic-safe naming).

    "changed" means the LLM changed the value and declared a reason —
    it NEVER means "improved". Improvement is decided only by blind
    adjudication. "repair" is deterministic_repair: the legacy value
    failed a candidate-contract check the candidate passes (contract
    conformance, not semantic approval).
    """
    if category in ("preserved", "preserved_implicit",
                    "redundant_replace"):
        return "legacy_preserved"
    if category == "repair":
        return "deterministic_repair"
    if category in ("justified_nullification",
                    "unjustified_nullification", "remain_null"):
        return "null"
    return "llm_changed"


def request_field_decisions(seed_cursor, cand_cursor, client, model,
                            max_retries=3):
    compact = {f: seed_cursor.get(f) for f in FIELDS}
    compact_c = {f: cand_cursor.get(f) for f in FIELDS}
    prompt = DECISION_PROMPT.format(
        fields=", ".join(FIELDS),
        legacy=json.dumps(compact, ensure_ascii=False, indent=1),
        candidate=json.dumps(compact_c, ensure_ascii=False, indent=1))
    last = None
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config={"temperature": 0,
                        "response_mime_type": "application/json"})
            return json.loads(_extract_json(resp.text))
        except Exception as exc:  # noqa: BLE001 - retry network/flakes
            last = exc
            time.sleep(2 * (attempt + 1))
    raise last


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


def _jitter(base, span=1.0):
    return base + random.uniform(0, span)


class QuotaError(Exception):
    pass


def generate_with_quota(client, model, prompt, ladder,
                        watchdog=600):
    """One generate call with paced 429 ladder. Raises QuotaError."""
    start = time.monotonic()
    for step in list(ladder) + [ladder[-1]] * 3:
        if watchdog and time.monotonic() - start > watchdog:
            raise QuotaError("watchdog: no successful call within "
                             "%ss" % watchdog)
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config={"temperature": 0})
            return resp
        except Exception as exc:  # noqa: BLE001
            status = getattr(exc, "code", None)
            if status in (429, "RESOURCE_EXHAUSTED",
                          "429 RESOURCE_EXHAUSTED"):
                time.sleep(_jitter(step))
                continue
            raise
    raise QuotaError("quota ladder exhausted")


def run_seeded(config, identities=None, out_dir=None, decisions=True,
               client=None):
    """Main loop. identities: subset list of {'lemma','pos','cefr'}.
    Defaults to the full snapshot. Returns provenance list summary."""
    seeds = load_seed_snapshot(config["seed_snapshot"])
    index = {"%s/%s" % (s["lemma"].strip().lower(),
                        (s.get("pos") or "").strip().lower()): s
             for s in seeds}

    prompt_path = os.path.join(ROOT_DIR, config["prompt_path"])
    with open(prompt_path, encoding="utf-8") as f:
        prompt_text = f.read()
    import hashlib
    prompt_hash = hashlib.sha256(
        prompt_text.encode("utf-8")).hexdigest()

    if identities is None:
        identities = [{"lemma": s["lemma"], "pos": s["pos"],
                       "cefr": s["seed"].get("cefr")} for s in seeds]

    out_dir = out_dir or config["output_dir"]
    raw_dir = os.path.join(out_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    provenance_path = os.path.join(out_dir,
                                   "seeded_generation_provenance.jsonl")
    progress_path = os.path.join(out_dir, "progress.json")

    progress = {}
    if os.path.exists(progress_path):
        with open(progress_path, encoding="utf-8") as f:
            progress = json.load(f)

    ladder = config.get("quota_ladder", [15, 30, 60, 120])
    pacing = config.get("pacing_seconds", 4)
    model = config["model_id"]

    done = list(progress.get("items", {}).keys())
    provenance_out = []
    for identity in identities:
        key = "%s/%s" % (identity["lemma"].strip().lower(),
                         (identity.get("pos") or "").strip().lower())
        if key in done:
            continue
        seed = index[key]
        seed_blob = seed["seed"]
        prompt = build_generation_prompt(identity, seed_blob, prompt_text)
        try:
            resp = generate_with_quota(
                client, model, prompt, ladder,
                watchdog=config.get("watchdog_seconds", 600))
            raw_text = resp.text
            out = parse_candidate(raw_text)
            cursor, arm = renormalize_candidate(out)
            checks, artifact_pass = validate_seeded_candidate(
                out, identity, cursor)
            decisions_out = None
            decisions_status = "not_requested"
            if decisions:
                try:
                    decisions_out = request_field_decisions(
                        seed_blob, cursor, client, model)
                    decisions_status = "ok"
                except Exception as exc:  # noqa: BLE001
                    decisions_out = None
                    decisions_status = "error: %s" % exc
            pres = seed_preservation_report(
                seed_blob, cursor, identity["lemma"],
                field_decisions=decisions_out)
            source_type = {}
            for f in FIELDS:
                source_type[f] = source_type_for(
                    pres["fields"][f]["category"],
                    (decisions_out or {}).get(f, {}).get("action"))
            entry = {
                "identity": {"lemma": identity["lemma"],
                             "pos": identity.get("pos"),
                             "cefr": identity.get("cefr")},
                "prompt_hash": prompt_hash,
                "model": model,
                "artifact_pass": artifact_pass,
                "validator": checks,
                "preservation": pres,
                "field_decisions": decisions_out,
                "decisions_status": decisions_status,
                "source_type": source_type,
            }
            with open(os.path.join(raw_dir, key.replace("/", "__")
                                   + ".json"),
                      "w", encoding="utf-8") as f:
                json.dump({"identity": identity, "candidate": out,
                           "arm": arm}, f, ensure_ascii=False, indent=1)
            with open(provenance_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False,
                                   sort_keys=True) + "\n")
            done.append(key)
            progress.setdefault("items", {})[key] = {
                "status": "success",
                "artifact_pass": artifact_pass}
            with open(progress_path, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False, indent=1)
            provenance_out.append(entry)
            print("ok %s (pass=%s)" % (key, artifact_pass))
        except QuotaError as qe:
            progress.setdefault("items", {})[key] = {
                "status": "quota_stop",
                "quota_ladder_exhausted": True}
            with open(progress_path, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False, indent=1)
            print("QUOTA STOP at %s: %s" % (key, qe))
            break
        except Exception as exc:  # noqa: BLE001
            progress.setdefault("items", {})[key] = {"status": "error",
                                                     "message": str(exc)}
            with open(progress_path, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False, indent=1)
            print("ERR %s: %s" % (key, exc))
            continue
        if pacing:
            time.sleep(_jitter(pacing))

    return provenance_out