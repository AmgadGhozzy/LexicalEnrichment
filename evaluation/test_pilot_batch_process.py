"""Tests for batch output processing (ticket 12).

Fixtures only: MODEL_TEXT success, empty-payload infra class,
unparseable output, validator-findings path. No network, no DB.
"""

import json
import os
import sys
import tempfile
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.pilot_batch_process import extract_model_text, process_row
from evaluation.run_provenance import read_history
from evaluation.utils import load_json

SCHEMA = load_json(os.path.join(
    ROOT_DIR, "evaluation", "prompts", "schemas",
    "lexical_output.v1.1-candidate.json"))
META = {"manifest_id": "pilot_manifest_v1", "manifest_hash": "abc123"}
ENTRY = {"id": 14, "lemma": "w", "pos": "noun", "stratum": ["A1", "noun"],
         "cefr_evidence_legacy": "A1", "frequency_band_legacy": 4,
         "ielts_overlap": False}


def good_output():
    return {
        "id": 14, "lemma": "w", "pos": "noun", "cefr_level": "A1",
        "difficulty_score": "3", "category": "General / Common",
        "ai_confidence": 0.9, "phonetic_us": "w", "phonetic_uk": None,
        "phonetic_ar": "و", "definition_en": "a w thing",
        "explanation_ar": "شرح", "mnemonic_ar": None,
        "collocations": [], "synonyms": [], "antonyms": [],
        "related_words": {"en": [], "ar": []},
        "word_family": {"noun": "w", "verb": "", "adj": "", "adv": ""},
        "translations": {"arabic_ar": "و", "french_fr": None,
                         "german_de": None, "spanish_es": None,
                         "chinese_zh": None, "russian_ru": None,
                         "portuguese_pt": None, "japanese_ja": None,
                         "italian_it": None, "turkish_tr": None},
        "examples": [
            {"example_text": "I saw the w.", "intended_cefr": "A1"},
            {"example_text": "The w is here.", "intended_cefr": "A1"},
            {"example_text": "We like the w.", "intended_cefr": "A1"}],
        "senses": [{
            "sense_no": 1, "definition_en": "a w thing",
            "short_def_en": "w", "definition_ar": "شيء",
            "is_primary": True, "register": "Neutral",
            "primary_sense": "Action", "semantic_tags": ["#A", "#B", "#C"],
            "usage_note": "", "mnemonic_ar": None}],
    }


def batch_row(key, text=None):
    if text is None:
        return {"key": key, "response": {}}
    return {"key": key,
            "response": {"candidates": [{"content": {"parts": [
                {"text": text}]}}]}}


class TestProcess(unittest.TestCase):
    def process(self, row):
        with tempfile.TemporaryDirectory() as tmp:
            rep = process_row(
                row, dict(ENTRY), META, SCHEMA,
                os.path.join(tmp, "history.jsonl"), tmp,
                run_id="RUN-T", job_id="JOB-T")
            hist = os.path.join(tmp, "history.jsonl")
            rows = read_history(hist) if os.path.exists(hist) else []
            return rep, rows

    def test_extract_model_text(self):
        ok, text = extract_model_text(batch_row("k", "hi"))
        self.assertTrue(ok)
        self.assertEqual(text, "hi")
        for bad in (batch_row("k"), batch_row("k", "  "),
                    {"key": "k"}):
            ok, cls = extract_model_text(bad)
            self.assertFalse(ok)
            self.assertEqual(cls, "empty_payload")

    def test_success_path(self):
        rep, hist = self.process(
            batch_row("PILOT-V1-CAND-14", json.dumps(good_output())))
        self.assertIn(rep["status"], ("ok", "partial"))
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["run"].get("batch_job_id"), "JOB-T")

    def test_empty_payload_no_attribution(self):
        rep, hist = self.process(batch_row("PILOT-V1-CAND-14"))
        self.assertEqual(rep["status"], "failed")
        self.assertEqual(rep["failure_class"],
                         "infrastructure_empty_payload")
        self.assertEqual(hist, [])

    def test_unparseable(self):
        rep, hist = self.process(batch_row("k", "not json{"))
        self.assertEqual(rep["status"], "failed")
        self.assertEqual(rep["failure_class"], "unparseable_output")
        self.assertEqual(hist, [])


if __name__ == "__main__":
    unittest.main()
