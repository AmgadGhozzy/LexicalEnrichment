"""Unit tests for the seeded generator (BT-15 Challenger build).
No network: parsing, renormalization, deterministic validation,
source_type mapping, and quota-loop behavior with a stub client."""

import json
import os
import sys
import tempfile
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation import seeded_generator as sg

IDENTITY = {"lemma": "refuse", "pos": "verb", "cefr": "A2"}


def _sample_out(strip=None):
    out = {
        "lemma": "refuse", "pos": "verb", "cefr": "A2",
        "definition_en": "to say no to something you do not want to do",
        "explanation_ar": "يرفض",
        "senses": [{"sense": "v1", "definition": "to decline"}],
        "examples": [
            {"example_text": "I refuse to go outside."},
            {"example_text": "We refuse to pay the fine."},
            {"example_text": "They refuse to stay quiet."},
        ],
        "translations": {"arabic_ar": "يرفض"},
        "relations": {"synonyms": ["decline"], "antonyms": ["accept"],
                      "collocations": ["refuse to do"]},
        "mnemonic": "Say it like a firm no: ref-use",
        "phonetic_us": "rɪˈfjuːz", "phonetic_uk": "rɪˈfjuːz",
        "syllables": "re-fuse",
        "semantic_tags": ["communication"],
        "ai_confidence": 0.9,
    }
    if strip:
        for s in strip:
            out.pop(s, None)
    return out


class TestParseAndRename(unittest.TestCase):
    def test_parse_fenced_json(self):
        text = '```json\n{"a": 1}\n```'
        self.assertEqual(sg.parse_candidate(text), {"a": 1})

    def test_parse_plain_json(self):
        self.assertEqual(sg.parse_candidate('{"a": 2}'), {"a": 2})

    def test_renormalize_translations_and_relations(self):
        out = _sample_out()
        cursor, arm = sg.renormalize_candidate(out)
        self.assertEqual(cursor["translations"], "يرفض")
        self.assertEqual(cursor["synonyms"], ["decline"])
        self.assertEqual(cursor["mnemonic"], "Say it like a firm no: ref-use")
        self.assertEqual(arm["translations"], {"arabic_ar": "يرفض"})
        self.assertEqual(arm["mnemonic_ar"], "Say it like a firm no: ref-use")

    def test_renormalize_translations_plain_string(self):
        out = _sample_out()
        out["translations"] = "يرفض"
        cursor, _ = sg.renormalize_candidate(out)
        self.assertEqual(cursor["translations"], "يرفض")

    def test_renormalize_mnemonic_aliases(self):
        out = _sample_out()
        out.pop("mnemonic")
        out["mnemonic_ar"] = "alt"
        cursor, arm = sg.renormalize_candidate(out)
        self.assertEqual(cursor["mnemonic"], "alt")
        self.assertEqual(arm["mnemonic_ar"], "alt")


class TestValidateSeeded(unittest.TestCase):
    def test_sample_passes(self):
        out = _sample_out()
        cursor, _ = sg.renormalize_candidate(out)
        checks, ok = sg.validate_seeded_candidate(out, IDENTITY, cursor)
        self.assertTrue(ok, checks)

    def test_identity_lock(self):
        out = _sample_out()
        out["cefr"] = "B2"
        cursor, _ = sg.renormalize_candidate(out)
        checks, _ = sg.validate_seeded_candidate(out, IDENTITY, cursor)
        self.assertEqual(checks["identity_cefr"]["status"], "fail")

    def test_missing_target_candidate_fails(self):
        out = _sample_out()
        out["examples"] = [{"example_text": "They said no"},
                           {"example_text": "She said no"},
                           {"example_text": "He said no"}]
        cursor, _ = sg.renormalize_candidate(out)
        checks, _ = sg.validate_seeded_candidate(out, IDENTITY, cursor)
        self.assertEqual(checks["examples_contain_target"]["status"], "fail")

    def test_one_example_counts_failure(self):
        out = _sample_out()
        out["examples"] = [{"example_text": "I refuse to go outside."}]
        cursor, _ = sg.renormalize_candidate(out)
        checks, _ = sg.validate_seeded_candidate(out, IDENTITY, cursor)
        self.assertEqual(checks["examples_count"]["status"], "fail")


class TestSourceType(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(sg.source_type_for("preserved", "preserve"),
                         "legacy_preserved")
        self.assertEqual(sg.source_type_for("changed", "improve"),
                         "llm_changed")
        self.assertEqual(sg.source_type_for("unjustified_change", None),
                         "llm_changed")
        self.assertEqual(sg.source_type_for("regression", None),
                         "llm_changed")
        self.assertEqual(sg.source_type_for("repair", "improve"),
                         "deterministic_repair")
        self.assertEqual(sg.source_type_for("remain_null", "null"), "null")
        self.assertEqual(sg.source_type_for("justified_nullification",
                                            "null"), "null")
        self.assertEqual(sg.source_type_for("unjustified_nullification",
                                            "null"), "null")


class TestLoop(unittest.TestCase):
    def _stub_client(self, quota_first=False):
        class Resp:
            text = json.dumps(_sample_out())

        class Models:
            def __init__(self, client):
                self._client = client

            def generate_content(self, model, contents, config=None):
                self._client.calls += 1
                if self._client.quota_first and self._client.calls == 1:
                    raise _Quota()
                return Resp()

        class Client:
            def __init__(self):
                self.calls = 0
                self.quota_first = quota_first
                self.models = Models(self)

        return Client()

    def test_run_two_identities(self):
        cfg = {
            "seed_snapshot": os.path.join(
                tempfile.mkdtemp(), "seed.jsonl"),
            "prompt_path": "evaluation/prompts/"
                           "lexical_enrichment_seeded_v1.txt",
            "output_dir": os.path.join(tempfile.mkdtemp(), "gen"),
            "model_id": "fake", "pacing_seconds": 0,
            "quota_ladder": [1], "watchdog_seconds": 30,
        }
        with open(cfg["seed_snapshot"], "w", encoding="utf-8") as f:
            for lemma in ("refuse", "fish"):
                rec = {"lemma": lemma, "pos": "verb",
                       "seed": {"definition_en": "legacy %s val" % lemma,
                                "explanation_ar": "شرح",
                                "examples": {"1": "I %s here." % lemma,
                                             "2": "We %s now." % lemma,
                                             "3": "You %s too." % lemma},
                                "translations": "بلد",
                                "synonyms": [], "antonyms": [],
                                "collocations": [], "mnemonic": None,
                                "cefr": "A2"}}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        ids = [{"lemma": "refuse", "pos": "verb", "cefr": "A2"},
               {"lemma": "fish", "pos": "verb", "cefr": "A2"}]
        client = self._stub_client()
        out = sg.run_seeded(cfg, identities=ids, decisions=False,
                            client=client)
        self.assertEqual(len(out), 2)
        by_lemma = {e["identity"]["lemma"]: e for e in out}
        # refuse identity matches the stub candidate exactly -> passes.
        self.assertTrue(by_lemma["refuse"]["artifact_pass"])
        # fish identity receives the refuse candidate -> identity lock fails.
        self.assertFalse(by_lemma["fish"]["artifact_pass"])

    def test_quota_first_retries_then_succeeds(self):
        cfg = {
            "seed_snapshot": os.path.join(tempfile.mkdtemp(), "s.jsonl"),
            "prompt_path": "evaluation/prompts/"
                           "lexical_enrichment_seeded_v1.txt",
            "output_dir": os.path.join(tempfile.mkdtemp(), "g"),
            "model_id": "fake", "pacing_seconds": 0,
            "quota_ladder": [1], "watchdog_seconds": 30,
        }
        with open(cfg["seed_snapshot"], "w", encoding="utf-8") as f:
            rec = {"lemma": "refuse", "pos": "verb",
                   "seed": {"definition_en": "legacy",
                            "explanation_ar": "شرح", "examples": {},
                            "translations": "", "synonyms": [],
                            "antonyms": [], "collocations": [],
                            "mnemonic": None, "cefr": "A2"}}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        client = self._stub_client(quota_first=True)
        out = sg.run_seeded(cfg, identities=IDENTITY.keys() and
                            [IDENTITY], decisions=False, client=client)
        self.assertEqual(len(out), 1)


class _Quota(Exception):
    code = 429


if __name__ == "__main__":
    unittest.main()