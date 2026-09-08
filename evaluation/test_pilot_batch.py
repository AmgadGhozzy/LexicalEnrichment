"""Tests for the pilot batch input builder (ticket 12).

Locks: frozen-sample intactness, v2.2.3 config fidelity,
manifest/master drift refusal. Fixtures only.
"""

import json
import os
import sys
import tempfile
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.pilot_batch import V223, build_envelope, build_input

TEMPLATE = "lemma={lemma} pos={pos} cefr={cefr} id={id}"
SCHEMA = {"type": "object", "properties": {}}
ENTRY = {"id": 14, "lemma": "w", "pos": "noun", "stratum": ["A1", "noun"],
         "cefr_evidence_legacy": "A1", "frequency_band_legacy": 4,
         "ielts_overlap": False}


class TestBatchInput(unittest.TestCase):
    def test_envelope_shape(self):
        env = build_envelope(ENTRY, (14, "w", "noun"), TEMPLATE, SCHEMA)
        self.assertEqual(env["key"], "PILOT-V1-CAND-14")
        gc = env["request"]["generationConfig"]
        self.assertEqual(gc["temperature"], 1.0)
        self.assertEqual(gc["maxOutputTokens"], 8192)
        self.assertEqual(gc["responseMimeType"], "application/json")
        self.assertEqual(gc["thinkingConfig"], {"thinkingLevel": "low"})
        self.assertNotIn("tools", env["request"])  # grounding off
        self.assertIn("lemma=w pos=noun cefr=A1 id=14",
                      env["request"]["contents"][0]["parts"][0]["text"])

    def test_drift_refused(self):
        with self.assertRaises(ValueError):
            build_envelope(ENTRY, (14, "w", "verb"), TEMPLATE, SCHEMA)
        with self.assertRaises(ValueError):
            build_envelope(ENTRY, (15, "w", "noun"), TEMPLATE, SCHEMA)

    def test_frozen_sample_intact(self):
        entries = [dict(ENTRY, id=i, lemma="w%d" % i) for i in (1, 2, 3)]
        lookup = {i: (i, "w%d" % i, "noun") for i in (1, 2, 3)}
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "in.jsonl")
            rec = build_input(entries, lookup, TEMPLATE, SCHEMA, out)
            self.assertEqual(rec["count"], 3)
            self.assertEqual(rec["manifest_ids"], [1, 2, 3])
            self.assertEqual(rec["config"]["prompt_version"], "2.2.3")

    def test_missing_master_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_input([ENTRY], {}, TEMPLATE, SCHEMA,
                            os.path.join(tmp, "in.jsonl"))


if __name__ == "__main__":
    unittest.main()
