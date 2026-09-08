"""Tests for the pilot runner (ticket 12).

Stub generation only (no network): success path, invalid JSON,
validator-failure path, non-single-word input refusal. Real Vertex
calls happen in execution scope, never in tests.
"""

import json
import os
import sys
import tempfile
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.pilot_run import EXPERIMENT_ID, run_one
from evaluation.run_provenance import read_history
from evaluation.utils import load_json
from evaluation.artifact_validator import validate_artifact
from evaluation.lexical_validator import convert_gemini_schema

SCHEMA = load_json(os.path.join(
    ROOT_DIR, "evaluation", "prompts", "schemas",
    "lexical_output.v1.1-candidate.json"))

TEMPLATE = "lemma={lemma} pos={pos} cefr={cefr} id={id}"
META = {"manifest_id": "pilot_manifest_v1", "manifest_hash": "abc123"}

ENTRY = {"id": 14, "lemma": "testword", "pos": "noun",
         "stratum": ["A1", "noun"], "cefr_evidence_legacy": "A1",
         "frequency_band_legacy": 4, "ielts_overlap": False}


def good_output():
    return {
        "id": 14, "lemma": "testword", "pos": "noun",
        "cefr_level": "A1", "difficulty_score": "3",
        "category": "General / Common", "ai_confidence": 0.9,
        "phonetic_us": "testw3d", "phonetic_uk": "testw3d",
        "phonetic_ar": "تست", "definition_en": "a word for testing",
        "explanation_ar": "شرح", "examples": [
            {"example_text": "I saw the testword.",
             "intended_cefr": "A1"},
            {"example_text": "The testword is here.",
             "intended_cefr": "A1"},
            {"example_text": "We like the testword.",
             "intended_cefr": "A1"}],
        "mnemonic_ar": None, "collocations": [], "synonyms": [],
        "antonyms": [], "related_words": {"en": [], "ar": []},
        "word_family": {"noun": "testword", "verb": "", "adj": "",
                        "adv": ""},
        "translations": {"arabic_ar": "اختبار", "french_fr": None,
                         "german_de": None, "spanish_es": None,
                         "chinese_zh": None, "russian_ru": None,
                         "portuguese_pt": None, "japanese_ja": None,
                         "italian_it": None, "turkish_tr": None},
        "senses": [{
            "sense_no": 1,
            "definition_en": "a word used for testing",
            "short_def_en": "test word",
            "definition_ar": "كلمة للاختبار",
            "is_primary": True,
            "register": "Neutral",
            "primary_sense": "Action",
            "semantic_tags": ["#Test", "#Word", "#Trial"],
            "usage_note": "",
            "mnemonic_ar": None,
        }],
    }


class TestPilotRun(unittest.TestCase):
    def run_entry(self, entry, text_fn):
        with tempfile.TemporaryDirectory() as tmp:
            rep = run_one(dict(entry), META, TEMPLATE, SCHEMA,
                          text_fn, tmp, "RUN-T")
            hist = os.path.join(tmp, "history.jsonl")
            return rep, read_history(hist) if os.path.exists(hist) else []

    def test_success_path(self):
        rep, hist = self.run_entry(
            ENTRY, lambda p: json.dumps(good_output()))
        self.assertIn(rep["status"], ("ok", "partial"))
        self.assertIsNotNone(rep["validator"])
        self.assertEqual(len(hist), 1)
        self.assertEqual(
            hist[0]["run"]["input_snapshot_hash"], "abc123")

    def test_invalid_json_is_failed_not_silent(self):
        rep, hist = self.run_entry(ENTRY, lambda p: "not json{")
        self.assertEqual(rep["status"], "failed")
        self.assertIn("error", rep)
        self.assertEqual(hist, [])

    def test_non_single_word_refused(self):
        bad = dict(ENTRY, lemma="solar system")
        rep, hist = self.run_entry(bad, lambda p: "{}")
        self.assertEqual(rep["status"], "failed")
        self.assertEqual(hist, [])

    def test_provenance_line_recorded(self):
        rep, _ = self.run_entry(
            ENTRY, lambda p: json.dumps(good_output()))
        if rep["status"] in ("ok", "partial"):
            self.assertEqual(rep["provenance_line"], 1)


def null_envelope():
    out = good_output()
    out["phonetic_uk"] = None
    out["senses"][0]["mnemonic_ar"] = None
    return {
        "candidate_id": "C-1",
        "experiment_id": EXPERIMENT_ID,
        "lexical_entry": {"lexical_id": "C-1", "lemma": "testword",
                          "pos": "noun", "cefr": "A1"},
        "runtime": {"status": "success"},
        "output": out,
        "provenance": {"output_hash": "x", "golden_set_hash": None,
                       "schema_version": "lexical_output.v1.1-candidate"},
    }


class TestNullableTransport(unittest.TestCase):
    """Locked NULL semantics must pass the frame check (BT-12 amend).

    phonetic_uk null (same-as-US) and mnemonic_ar null (no valid
    hook) are semantic outcomes, not schema violations. Both schema
    paths — raw Gemini-native and pre-converted — must agree.
    """

    def test_nulls_pass_raw_schema(self):
        env = null_envelope()
        from evaluation.utils import canonical_hash
        env["provenance"]["output_hash"] = canonical_hash(env["output"])
        _, failures, _ = validate_artifact(env, EXPERIMENT_ID, SCHEMA)
        self.assertEqual(
            [f for f in failures if f["code"] == "SCHEMA_VIOLATION"], [])

    def test_nulls_pass_preconverted_schema(self):
        env = null_envelope()
        from evaluation.utils import canonical_hash
        env["provenance"]["output_hash"] = canonical_hash(env["output"])
        _, failures, _ = validate_artifact(
            env, EXPERIMENT_ID, convert_gemini_schema(SCHEMA))
        self.assertEqual(
            [f for f in failures if f["code"] == "SCHEMA_VIOLATION"], [])

    def test_empty_string_still_string(self):
        # null != "": empty strings remain valid strings, and the
        # validator must not conflate the two states.
        env = null_envelope()
        env["output"]["phonetic_uk"] = ""
        from evaluation.utils import canonical_hash
        env["provenance"]["output_hash"] = canonical_hash(env["output"])
        _, failures, _ = validate_artifact(env, EXPERIMENT_ID, SCHEMA)
        self.assertEqual(
            [f for f in failures if f["code"] == "SCHEMA_VIOLATION"], [])


if __name__ == "__main__":
    unittest.main()
