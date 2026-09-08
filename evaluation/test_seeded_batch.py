"""Unit tests for the two-phase batch transport seam (seeded_batch).

Tests stay transport-agnostic: envelopes, remaining computation,
import mapping, artifact gate, and channel-tagged provenance are
exercised with synthetic records, no Vertex/GCS calls.
"""

import json
import os

import pytest

from evaluation import seeded_batch as sb

MINIMAL_CANDIDATE = {
    "lemma": "opto",
    "pos": "verb",
    "cefr": "B1",
    "definition_en": "to make something better or more valuable",
    "explanation_ar": "تحسين شيء وجعله أفضل",
    "senses": [{"name": "#common", "examples": []}],
    "examples": [
        {"example_text": "They opted to improve the opto system."},
        {"example_text": "An opto update helped everyone."},
        {"example_text": "She uses opto every morning."},
    ],
    "translations": {"arabic_ar": "حسّن"},
    "relations": {"synonyms": ["improve"], "antonyms": ["worsen"],
                  "collocations": ["opto well"]},
    "mnemonic": "opto hooks onto 'optimize'",
    "phonetic_us": "opto",
    "phonetic_uk": None,
    "syllables": "op-to",
    "semantic_tags": ["#improvement"],
    "ai_confidence": 0.9,
}

SEED_BLOB = {
    "definition_en": "old gloss",
    "explanation_ar": "شرح قديم",
    "examples": [],
    "translations": "قديم",
    "synonyms": ["legacy-syn"],
    "antonyms": [],
    "collocations": [],
    "mnemonic": None,
    "category": "noun",
    "cefr": "B1",
}

IDENTITY = {"lemma": "opto", "pos": "verb", "cefr": "B1"}


def _candidate_json(candidate=None):
    return json.dumps(candidate or MINIMAL_CANDIDATE, ensure_ascii=False)


def _record(key, text):
    return {"key": key, "response": {"candidates": [
        {"content": {"parts": [{"text": text}]}}]}}


def _identity_for_submitted(key):
    return {"key": key.replace("__", "/"),
            "lemma": key.split("__")[0], "pos": key.split("__")[1],
            "cefr": "B1"}


@pytest.fixture
def index(tmp_path):
    idx = {"opto/verb": {"lemma": "opto", "pos": "verb", "cefr": "B1",
                         "seed": dict(SEED_BLOB)}}
    sb.RUN_DIR = str(tmp_path / "run")
    sb.BATCH_SUBDIR = str(tmp_path / "run" / "batch")
    return idx


def test_compute_remaining_excludes_done():
    progress = {"items": {"opto/verb": {"status": "success"},
                          "other/noun": {"status": "error"}}}
    identities = [IDENTITY, {"lemma": "other", "pos": "noun", "cefr": "A2"}]
    remaining = sb.compute_remaining(identities, progress)
    assert [sb.key_of(i) for i in remaining] == ["other/noun"]


def test_generation_envelope_no_schema_no_mime():
    prompt_text = "SEED PROMPT"
    reqs = sb.build_generation_requests(
        [IDENTITY], {"opto/verb": {"seed": dict(SEED_BLOB)}}, prompt_text)
    assert len(reqs) == 1
    env = reqs[0]
    assert env["key"] == "opto__verb"
    gc = env["request"]["generationConfig"]
    assert gc == {"temperature": 0}
    assert "responseSchema" not in gc and "responseMimeType" not in gc
    text = env["request"]["contents"][0]["parts"][0]["text"]
    assert "SEED PROMPT" in text and "opto" in text


def test_decision_envelope_json_mime_and_cursor():
    raw = {"identity": IDENTITY, "candidate": MINIMAL_CANDIDATE,
           "arm": {}}
    reqs = sb.build_decision_requests(
        ["opto/verb"], {"opto/verb": {"seed": dict(SEED_BLOB)}},
        lambda key: raw)
    assert len(reqs) == 1
    env = reqs[0]
    assert env["key"] == "opto__verb"
    gc = env["request"]["generationConfig"]
    assert gc.get("responseMimeType") == "application/json"
    text = env["request"]["contents"][0]["parts"][0]["text"]
    assert '"legacy_state"' in text
    assert "LEGACY:" in text and "CANDIDATE:" in text
    assert "improve" in text and "legacy-syn" in text


def test_generation_import_ok_channels_batch(index):
    lines = [json.dumps(_record("opto__verb", _candidate_json()))]
    submitted = {"opto__verb": _identity_for_submitted("opto__verb")}
    outcomes = sb.import_generation_records(
        lines, submitted, index, "phash", "gemini-3.8-flash",
        {"job_id": "jobs/a1", "input_gcs": "gs://in",
         "output_gcs": "gs://out"})
    key, entry, err, art_pass, candidate, arm = outcomes[0]
    assert err is None and art_pass is True
    assert entry["channel"] == "batch" and entry["phase"] == "generation"
    assert entry["artifact_pass"] is True
    assert entry["candidate_hash"]
    assert candidate["relations"]["synonyms"] == ["improve"]
    assert arm["translations"]["arabic_ar"] == "حسّن"


def test_generation_import_gate_rejects_identity_mismatch(index):
    bad = dict(MINIMAL_CANDIDATE)
    bad["lemma"] = "wrong"
    line = json.dumps(_record("opto__verb", json.dumps(bad)))
    outcomes = sb.import_generation_records(
        [line], {"opto__verb": _identity_for_submitted("opto__verb")},
        index, "phash", "m", {"job_id": "j", "input_gcs": "i",
                              "output_gcs": "o"})
    key, entry, err, art_pass, candidate, arm = outcomes[0]
    assert entry is not None
    assert art_pass is False
    assert entry["artifact_pass"] is False


def test_generation_import_bad_parse_is_error(index):
    line = json.dumps(_record("opto__verb", "{not json"))
    outcomes = sb.import_generation_records(
        [line], {"opto__verb": _identity_for_submitted("opto__verb")},
        index, "phash", "m", {"job_id": "j", "input_gcs": "i",
                              "output_gcs": "o"})
    key, entry, err, art_pass, candidate, arm = outcomes[0]
    assert entry is None
    assert art_pass is False
    assert err and "parse_failed" in err


def test_decision_import_ok_outputs_preservation(index):
    raw = {"identity": IDENTITY, "candidate": MINIMAL_CANDIDATE,
           "arm": {}}
    (index["opto/verb"]["seed"])
    decisions = {"definition_en": {"action": "improve", "reason": "richer",
                                   "legacy_state": "non_null",
                                   "legacy_defect": True,
                                   "replacement_superiority": True,
                                   "evidence": "legacy gloss is vague"}}
    line = json.dumps(_record("opto__verb", json.dumps(decisions)))
    sb._load_raw = lambda key: raw  # noqa: SLF001
    outcomes = sb.import_decision_records(
        [line], {"opto__verb": _identity_for_submitted("opto__verb")},
        index, "m", {"job_id": "jobs/b1"})
    key, entry, err = outcomes[0]
    assert err is None
    assert entry["phase"] == "decision" and entry["channel"] == "batch"
    assert entry["decisions_status"] == "ok"
    assert entry["field_decisions"]["definition_en"]["action"] == "improve"
    assert entry["source_type"]["definition_en"] == "llm_changed"
    assert entry["preservation"]["fields"]["definition_en"]["category"]


def test_decision_import_preserve_is_legacy_preserved(index):
    raw = {"identity": IDENTITY, "candidate": MINIMAL_CANDIDATE,
           "arm": {}}
    seed = index["opto/verb"]["seed"]
    seed["definition_en"] = MINIMAL_CANDIDATE["definition_en"]
    cand = dict(MINIMAL_CANDIDATE)
    cand["relations"] = {"synonyms": ["improve"], "antonyms": ["worsen"],
                         "collocations": ["opto well"]}
    raw["candidate"] = cand
    decisions = {"definition_en": {"action": "preserve", "reason": "",
                                   "legacy_state": "non_null",
                                   "legacy_defect": False,
                                   "replacement_superiority": False,
                                   "evidence": ""}}
    line = json.dumps(_record("opto__verb", json.dumps(decisions)))
    sb._load_raw = lambda key: raw  # noqa: SLF001
    outcomes = sb.import_decision_records(
        [line], {"opto__verb": _identity_for_submitted("opto__verb")},
        index, "m", {"job_id": "j"})
    entry = outcomes[0][1]
    assert entry["source_type"]["definition_en"] == "legacy_preserved"


def test_batch_generation_pass_keys_selects_only_batch(tmp_path):
    sb.RUN_DIR = str(tmp_path / "run")
    path = os.path.join(sb.RUN_DIR, "seeded_generation_provenance.jsonl")
    os.makedirs(sb.RUN_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"identity": {"lemma": "drop", "pos": "verb"},
                            "phase": "generation", "channel": "batch",
                            "artifact_pass": False}) + "\n")
        f.write(json.dumps({"identity": {"lemma": "opto", "pos": "verb"},
                            "phase": "generation", "channel": "batch",
                            "artifact_pass": True}) + "\n")
        f.write(json.dumps({"identity": {"lemma": "keep", "pos": "noun"},
                            "artifact_pass": True}) + "\n")
    keys = sb._batch_generation_pass_keys()
    assert keys == ["opto/verb"]