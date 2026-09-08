"""Unit tests for the batch AI-judge transport (seeded_judge)."""

import json

from evaluation import seeded_judge as sj


def _item():
    return {
        "eval_id": "eval_seeded348_v1-0001",
        "lemma": "opto", "pos": "verb",
        "armA": {"definition": "one gloss"},
        "armB": {"definition": "two gloss"},
        "ballot": {"fields": {}, "critical_errors": {}},
    }


def _valid_ballot():
    return {
        "fields": {"definition": "tie", "arabic_explanation": "tie",
                   "sense_separation": "cannot-judge",
                   "examples": "A-better",
                   "translations": "B-better", "relations": "tie",
                   "mnemonic": "tie"},
        "critical_errors": {"wrong_meaning": {"side": None, "evidence": ""},
                            "misleading_arabic": {"side": None,
                                                  "evidence": ""},
                            "invalid_relation_synonym": {"side": "A",
                                                         "evidence": "x"},
                            "example_semantic_error": {"side": None,
                                                       "evidence": ""},
                            "target_word_violation": {"side": None,
                                                      "evidence": ""},
                            "fabricated_etymology_mnemonic": {"side": None,
                                                              "evidence": ""},
                            "cefr_learner_mismatch": {"side": None,
                                                      "evidence": ""}},
        "note": "ok",
    }


def _rec(key, text):
    return {"key": key, "response": {"candidates": [
        {"content": {"parts": [{"text": text}]}}]}}


def test_build_requests_pins_config_and_prompt_allowlist():
    reqs = sj.build_requests([_item()])
    assert len(reqs) == 1
    env = reqs[0]
    assert env["key"] == "eval_seeded348_v1-0001"
    gc = env["request"]["generationConfig"]
    assert gc["temperature"] == 0.0
    assert gc["maxOutputTokens"] == 4000
    assert gc["responseMimeType"] == "application/json"
    assert gc["thinkingConfig"]["thinkingLevel"] == "low"
    text = env["request"]["contents"][0]["parts"][0]["text"]
    assert "You are a blind adjudicator" in text
    assert "eval_seeded348_v1-0001" in text
    # the model input = rubric + canonical blind view, nothing else
    from evaluation.ai_judge import serialize_blind_view
    assert text.endswith(serialize_blind_view(_item()))
    for banned in ("candidate_output", "legacy_row"):
        assert banned not in text


def test_import_ballots_accepts_valid_rejects_invalid():
    ok = json.dumps(_valid_ballot())
    bad = json.dumps({"fields": {"definition": "NOPE"},
                      "critical_errors": {}
                      if False else None})
    lines = [
        json.dumps(_rec("eval_seeded348_v1-0001", ok)),
        json.dumps(_rec("eval_seeded348_v1-0002", "not json")),
        json.dumps({"key": "eval_seeded348_v1-0003",
                    "error": {"code": 5}}),
    ]
    eval_ids = ["eval_seeded348_v1-0001", "eval_seeded348_v1-0002",
                "eval_seeded348_v1-0003"]
    judgments, rejects, malformed = sj.import_ballots(lines, eval_ids)
    assert len(judgments) == 1
    assert judgments["eval_seeded348_v1-0001"]["fields"]["translations"] \
        == "B-better"
    assert "eval_seeded348_v1-0002" in rejects
    assert "batch_api_error" in rejects["eval_seeded348_v1-0003"]
    assert rejects.get("eval_seeded348_v1-0003")
    assert malformed == 0


def test_import_ballots_marks_missing_as_reject():
    lines = [json.dumps(_rec("eval_seeded348_v1-0001",
                             json.dumps(_valid_ballot())))]
    judgments, rejects, _ = sj.import_ballots(
        lines, ["eval_seeded348_v1-0001", "eval_seeded348_v1-0002"])
    assert len(judgments) == 1
    assert rejects["eval_seeded348_v1-0002"] == "missing_output"


def test_import_ballots_counts_malformed_lines():
    lines = ["{bad json", "still bad"]
    judgments, rejects, malformed = sj.import_ballots(
        lines, ["a"])
    assert malformed == 2
    assert not judgments