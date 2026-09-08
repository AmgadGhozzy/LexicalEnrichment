"""Unit tests for the 348 blind-package builder."""

import json

from evaluation import build_seeded348_package as p

COMBINED = {"identity": {"lemma": "Alpha", "pos": "noun"}}
DECISION = {"identity": {"lemma": "beta", "pos": "verb"},
            "phase": "decision"}
GEN_ONLY = {"identity": {"lemma": "gamma", "pos": "adj"},
            "phase": "generation"}


def _prov_path(tmp_path, lines):
    path = tmp_path / "prov.jsonl"
    path.write_text("\n".join(
        json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return str(path)


def test_decided_identities_computed(tmp_path):
    path = _prov_path(tmp_path, [COMBINED, DECISION, GEN_ONLY])
    got = p.load_decided_identities(path)
    assert got == [("alpha", "noun"), ("beta", "verb")]


def test_package_build_blind_and_sides(tmp_path):
    items_src = [
        {"eval_key": "a/noun", "lemma": "a", "pos": "noun",
         "candidate_output": {
             "definition_en": "gloss",
             "explanation_ar": "شرح",
             "examples": [{"example_text": "a sample."}],
             "translations": {"arabic_ar": "ترجمة"},
             "synonyms": ["x"], "antonyms": [], "collocations": [],
             "mnemonic_ar": "hook"},
         "legacy_row": {
             "definitionEn": "old", "definitionAr": "قديم",
             "examples": json.dumps({"B1": ["legacy."]}),
             "arabicAr": "قديم", "synonyms": "[\"y\"]",
             "antonyms": "[]", "mnemonicAr": "old hook"}},
        {"eval_key": "b/verb", "lemma": "b", "pos": "verb",
         "candidate_output": {
             "definition_en": "gloss2", "explanation_ar": "شرح2",
             "examples": [{"example_text": "b sample."}],
             "translations": {"arabic_ar": "ترجمة2"},
             "synonyms": [], "antonyms": ["z"], "collocations": ["c"],
             "mnemonic_ar": None},
         "legacy_row": {
             "definitionEn": "old2", "definitionAr": "قديم2",
             "examples": {"A2": ["legacy2."]}, "arabicAr": "قديم2",
             "synonyms": [], "antonyms": "[\"z\"]", "mnemonicAr": None}},
    ]
    pkg, id_map = p.build_package_348(items_src)
    assert len(pkg) == 2 and len(id_map) == 2
    for it in pkg:
        assert set(it["armA"]) == set(it["armB"])
    assert sorted(id_map) == [it["eval_id"] for it in pkg]
    assert id_map[pkg[0]["eval_id"]]["candidate_key"] in (
        "a/noun", "b/verb")


def test_package_has_no_transport_keys():
    ok = {"items": [{"armA": {"definition": "a channel is a waterway"},
                     "armB": {"definition": "same gloss"}}]}
    p._assert_no_transport_keys(ok)
    bad = {"items": [{"armA": {"definition": "x"},
                      "channel": "batch"}]}
    try:
        p._assert_no_transport_keys(bad)
        raise AssertionError("expected transport-key rejection")
    except RuntimeError as exc:
        assert "channel" in str(exc)


def test_manifest_pins(tmp_path):
    path = _prov_path(tmp_path, [
        {"identity": {"lemma": "a", "pos": "n"},
         "artifact_pass": True, "validator": {},
         "prompt_hash": "h1"},
        {"identity": {"lemma": "a", "pos": "v"}, "phase": "decision",
         "artifact_pass": True, "validator": {}, "prompt_hash": "h1"}])
    ids = [("a", "n"), ("a", "v")]
    record = p.build_input_manifest(path, ids,
                                    {"run": "generated_356"})
    assert len(record["entries"]) == 2
    assert record["run"] == "generated_356"
    assert record["input_hash"]
    assert record["entries"][0]["prompt_hash"] == "h1"