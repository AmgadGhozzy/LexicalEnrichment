"""Tests for the seed snapshot extractor + preservation classifier.

EXP-SEEDED-001 (BT-15). No network, no DB in unit scope:
- transport-only mapping rules
- taxonomy locks and metric formulas
- legacy contract smoke (WordsMaster rows -> seed record)
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.seed_preservation import (
    FIELDS,
    classify_field,
    seed_preservation_report,
)
from evaluation.seed_snapshot import (
    _COLUMN_MAP, _META_MAP, build_seed_snapshot, row_to_seed,
    seed_sha256, write_seed_snapshot,
)

LEMMA = "refuse"
DEF = "to say no to something you do not want to do"
GOOD_EXAMPLES = ["I refuse to go outside.", "We refuse to pay the fine.",
                 "They refuse to stay quiet."]


class TestRowToSeed(unittest.TestCase):
    def test_transport_only_rename(self):
        row = {
            "wordEn": "refuse", "pos": "verb",
            "definitionEn": "to say no",
            "definitionAr": "يرفض",
            "mnemonicAr": "ذكّرني بكلمة refuse",
            "examples": '{"1": "They refuse to pay"}',
            "arabicAr": "يرفض",
            "usageNote": "v.",
            "phoneticUs": "/rɪˈfjuːz/", "phoneticUk": None,
            "syllabify": "ref-use",
            "synonyms": "[\"decline\"]",
            "antonyms": "", "collocations": None,
            "relatedWords": "[\"refusal\"]",
            "wordFamily": "{\"noun\": \"refusal\"}",
            "semanticTags": "[\"communication\"]",
            "category": "noun", "primarySense": "decline",
            "register": "formal",
        }
        seed = row_to_seed(row, "A2")
        self.assertEqual(seed["definition_en"], "to say no")
        self.assertEqual(seed["explanation_ar"], "يرفض")
        self.assertEqual(seed["mnemonic"], "ذكّرني بكلمة refuse")
        self.assertEqual(seed["translations"], "يرفض")
        self.assertEqual(seed["examples"], {"1": "They refuse to pay"})
        self.assertEqual(seed["category"], "noun")
        self.assertEqual(seed["primary_sense"], "decline")
        self.assertEqual(seed["register"], "formal")
        self.assertEqual(seed["phonetic_uk"], None)
        self.assertNotIn("rank", seed)
        self.assertNotIn("frequency", seed)
        self.assertNotIn("difficulty_score", seed)

    def test_identity_columns_never_in_seed(self):
        self.assertNotIn("rank", _COLUMN_MAP)
        self.assertNotIn("frequency", _COLUMN_MAP)
        self.assertNotIn("difficultyScore", _COLUMN_MAP)


class TestBuildSeedSnapshot(unittest.TestCase):
    def test_full_mapping_of_real_db(self):
        db = os.path.join(ROOT_DIR, "WordsMaster.db")
        self.assertTrue(os.path.exists(db), "WordsMaster.db present")
        specs = [
            {"lemma": "refuse", "pos": "verb", "cefr": "A2"},
            {"lemma": "no-such-word-xyz-1", "pos": "verb", "cefr": "B1"},
        ]
        records, report = build_seed_snapshot(db, specs)
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["found"], 1)
        self.assertEqual(len(report["missing"]), 1)
        rec = records[0]
        self.assertEqual(rec["lemma"], "refuse")
        self.assertEqual(rec["pos"], "verb")
        self.assertTrue(rec["seed"]["definition_en"])
        self.assertNotIn("rank", rec["seed"])

    def test_write_sidecar_sha256(self):
        tmpdir = tempfile.mkdtemp()
        out = os.path.join(tmpdir, "seed_snapshot_v1.jsonl")
        recs = [{"lemma": "a", "pos": "noun", "seed": {"definition_en": "X"}}]
        digest = write_seed_snapshot(recs, out)
        self.assertEqual(digest, seed_sha256(recs))
        self.assertEqual(len(open(out, encoding="utf-8").readlines()), 1)
        self.assertEqual(open(out + ".sha256", encoding="utf-8").read().strip(), digest)


class TestClassifyField(unittest.TestCase):
    def test_preserved(self):
        c, why = classify_field("definition_en", DEF, DEF,
                                "preserve", "already accurate", LEMMA)
        self.assertEqual(c, "preserved")

    def test_preserved_implicit_when_no_action(self):
        c, _ = classify_field("definition_en", DEF, DEF,
                              None, None, LEMMA)
        self.assertEqual(c, "preserved")

    def test_redundant_replace(self):
        c, _ = classify_field("definition_en", DEF, DEF,
                              "replace", "wants a better tone", LEMMA)
        self.assertEqual(c, "redundant_replace")

    def test_fill(self):
        c, _ = classify_field("mnemonic", None, "hard R like someone",
                              "improve", "", LEMMA)
        self.assertEqual(c, "fill")

    def test_remain_null(self):
        c, _ = classify_field("mnemonic", None, None, "null", "", LEMMA)
        self.assertEqual(c, "remain_null")
        c2, _ = classify_field("mnemonic", None, "   ", "null", "", LEMMA)
        self.assertEqual(c2, "remain_null")

    def test_translations_empty_string_is_null_pool(self):
        c, _ = classify_field("translations", "", "يرفض", "improve", "", LEMMA)
        self.assertEqual(c, "fill")
        c2, _ = classify_field("translations", "", "", "null", "", LEMMA)
        self.assertEqual(c2, "remain_null")

    def test_changed_with_reason(self):
        c, _ = classify_field("definition_en", DEF, "to decline firmly",
                              "improve", "cleaner phrasing", LEMMA,
                              replacement_superiority=True)
        self.assertEqual(c, "changed")

    def test_replace_without_superiority_is_unjustified(self):
        c, _ = classify_field("definition_en", DEF, "to decline firmly",
                              "improve", "cleaner phrasing", LEMMA)
        self.assertEqual(c, "unjustified_change")
        c2, _ = classify_field("definition_en", DEF, "to decline firmly",
                               "improve", "cleaner phrasing", LEMMA,
                               replacement_superiority=False)
        self.assertEqual(c2, "unjustified_change")

    def test_justified_nullification(self):
        c, _ = classify_field(
            "mnemonic", "a decent hook", None, "null",
            "removing a misleading hook", LEMMA,
            legacy_defect=True,
            evidence="the hook claims bucket comes from Arabic baqa'a",
            declared_legacy_state="non_null")
        self.assertEqual(c, "justified_nullification")

    def test_unjustified_nullification_no_defect_flag(self):
        c, _ = classify_field("mnemonic", "a decent hook", None, "null",
                              "removed mnemonic", LEMMA,
                              declared_legacy_state="non_null")
        self.assertEqual(c, "unjustified_nullification")

    def test_unjustified_nullification_vague_evidence(self):
        for vague in ("the mnemonic is not ideal",
                      "I cannot improve it",
                      "I prefer NULL",
                      "cleaner",
                      ""):
            c, why = classify_field(
                "mnemonic", "a decent hook", None, "null",
                "removed", LEMMA, legacy_defect=True,
                evidence=vague, declared_legacy_state="non_null")
            self.assertEqual(c, "unjustified_nullification", vague)

    def test_unjustified_nullification_no_declaration(self):
        c, _ = classify_field("mnemonic", "a decent hook", None, None,
                              None, LEMMA)
        self.assertEqual(c, "unjustified_nullification")

    def test_state_mismatch_conflicts(self):
        c, _ = classify_field("mnemonic", "a decent hook", None, "null",
                              "r", LEMMA, legacy_defect=True,
                              evidence="concrete defect named here",
                              declared_legacy_state="null")
        self.assertEqual(c, "field_decision_conflict")
        c2, _ = classify_field("mnemonic", None, None, "null", "", LEMMA,
                               declared_legacy_state="non_null")
        self.assertEqual(c2, "field_decision_conflict")

    def test_null_action_with_valid_value_conflicts(self):
        c, _ = classify_field("mnemonic", "a decent hook",
                              "another hook", "null", "r", LEMMA,
                              declared_legacy_state="non_null")
        self.assertEqual(c, "field_decision_conflict")

    def test_unjustified_change(self):
        c, _ = classify_field("definition_en", DEF, "to decline firmly",
                              "improve", None, LEMMA)
        self.assertEqual(c, "unjustified_change")
        c2, _ = classify_field("definition_en", DEF, "to decline firmly",
                              None, None, LEMMA)
        self.assertEqual(c2, "unjustified_change")

    def test_field_decision_conflict(self):
        c, _ = classify_field("definition_en", DEF, "to decline firmly",
                              "preserve", "", LEMMA)
        self.assertEqual(c, "field_decision_conflict")

    def test_regression_when_candidate_null(self):
        # 001A taxonomy: legacy-valid + candidate null is nullification,
        # never direct regression. Without defect evidence it is
        # unjustified (and enters the regression pool via the rate).
        c, _ = classify_field("definition_en", DEF, None,
                              "improve", "rewritten", LEMMA)
        self.assertEqual(c, "unjustified_nullification")

    def test_regression_when_candidate_fails_validation(self):
        c, _ = classify_field("examples",
                              GOOD_EXAMPLES,
                              ["wrong"], "improve", "new ones", LEMMA)
        self.assertEqual(c, "regression")

    def test_repair(self):
        c, _ = classify_field("mnemonic", "لا يوجد", "think of 'no' in French",
                              "improve", "fired the generic placeholder", LEMMA)
        self.assertEqual(c, "repair")

    def test_examples_preserved_dict_vs_candidate_list(self):
        legacy = {str(i + 1): e for i, e in enumerate(GOOD_EXAMPLES)}
        c, _ = classify_field("examples", legacy, GOOD_EXAMPLES,
                              "preserve", "", LEMMA)
        self.assertEqual(c, "preserved")


class TestReportMetrics(unittest.TestCase):
    def _seed(self):
        return {
            "definition_en": DEF,
            "explanation_ar": "يرفض",
            "examples": GOOD_EXAMPLES,
            "translations": "يرفض",
            "synonyms": ["decline", "reject"],
            "antonyms": ["accept"],
            "collocations": [],
            "mnemonic": "لا يوجد",
        }

    def test_metrics_formula(self):
        seed = self._seed()
        cand = {k: v for k, v in seed.items()}
        cand["mnemonic_ar"] = "Say it like a firm no: ref-use"
        report = seed_preservation_report(seed, cand, LEMMA,
                                          field_decisions={
                                              "mnemonic": {"action": "improve",
                                                           "reason": "generic placeholder"}})
        # legacy-good: definition, explanation, examples, translations,
        #              synonyms, antonyms = 6 ; collocations empty ->
        #              null pool ; mnemonic non-empty generic -> defective
        self.assertEqual(report["legacy_valid_pool"], 6)
        self.assertEqual(report["legacy_defective_pool"], 1)
        self.assertEqual(report["fields"]["collocations"]["category"],
                         "remain_null")
        self.assertEqual(report["fields"]["mnemonic"]["category"], "repair")
        self.assertEqual(report["preservation_precision"], 6 / 6)
        self.assertEqual(report["repair_recall"], 1 / 1)

    def test_regression_lowers_precision(self):
        seed = self._seed()
        cand = {k: v for k, v in seed.items()}
        cand["definition_en"] = None
        cand["mnemonic_ar"] = "Say it like a firm no: ref-use"
        report = seed_preservation_report(seed, cand, LEMMA,
                                          field_decisions={
                                              "mnemonic": {"action": "improve",
                                                           "reason": "generic placeholder"}})
        self.assertEqual(report["fields"]["definition_en"]["category"],
                         "unjustified_nullification")
        self.assertEqual(report["preservation_precision"], 5 / 6)
        self.assertEqual(report["regression_rate"], 1 / 6)

    def test_rates_on_mixed_report(self):
        # 8 fields: 6 valid (def/expl/trans/syn/ant/mnem-valid) +
        # 1 empty (collocations) + 1 defective (examples count!=3).
        seed = {
            "definition_en": DEF,
            "explanation_ar": "يرفض",
            "examples": ["only one refuse here"],
            "translations": "يرفض",
            "synonyms": ["decline"],
            "antonyms": ["accept"],
            "collocations": [],
            "mnemonic": "firm refusal hook",
        }
        cand = {
            "definition_en": DEF,
            "explanation_ar": "يرفض بصيغة أوضح",
            "examples": GOOD_EXAMPLES,
            "translations": "يرفض",
            "synonyms": ["decline"],
            "antonyms": ["accept"],
            "collocations": [],
            "mnemonic": None,
        }
        decisions = {
            "definition_en": {"action": "preserve", "reason": "",
                              "legacy_state": "non_null",
                              "legacy_defect": False,
                              "replacement_superiority": False,
                              "evidence": ""},
            "explanation_ar": {"action": "improve",
                               "reason": "clearer MSA phrasing",
                               "legacy_state": "non_null",
                               "legacy_defect": False,
                               "replacement_superiority": True,
                               "evidence": "legacy used dialectal verb"},
            "mnemonic": {"action": "null", "reason": "removed",
                         "legacy_state": "non_null",
                         "legacy_defect": True,
                         "replacement_superiority": False,
                         "evidence": "the hook asserts a false etymology"},
        }
        report = seed_preservation_report(seed, cand, LEMMA,
                                          field_decisions=decisions)
        # valid pool: definition, explanation, translations, synonyms,
        # antonyms, mnemonic = 6 ; examples defective ; collocations null.
        self.assertEqual(report["legacy_valid_pool"], 6)
        self.assertEqual(report["legacy_defective_pool"], 1)
        cats = {f: v["category"] for f, v in report["fields"].items()}
        self.assertEqual(cats["definition_en"], "preserved")
        self.assertEqual(cats["explanation_ar"], "changed")
        self.assertEqual(cats["mnemonic"], "justified_nullification")
        self.assertEqual(cats["examples"], "repair")
        self.assertEqual(report["preservation_precision"], 4 / 6)
        self.assertEqual(report["repair_recall"], 1 / 1)
        self.assertEqual(report["justified_change_rate"], 2 / 6)
        self.assertEqual(report["unjustified_change_rate"], 0 / 6)
        self.assertEqual(report["nullification_rate"], 1 / 6)
        self.assertEqual(report["unjustified_nullification_rate"], 0 / 6)
        self.assertEqual(report["regression_rate"], 0 / 6)

    def test_unjustified_nullification_enters_regression_pool(self):
        seed = {"definition_en": DEF, "explanation_ar": "يرفض",
                "examples": GOOD_EXAMPLES, "translations": "يرفض",
                "synonyms": ["decline"], "antonyms": ["accept"],
                "collocations": [], "mnemonic": "firm refusal hook"}
        cand = {k: v for k, v in seed.items()}
        cand["mnemonic"] = None
        report = seed_preservation_report(
            seed, cand, LEMMA,
            field_decisions={"mnemonic": {"action": "null",
                                          "reason": "removed",
                                          "legacy_state": "non_null",
                                          "legacy_defect": False,
                                          "evidence": ""}})
        self.assertEqual(report["fields"]["mnemonic"]["category"],
                         "unjustified_nullification")
        # valid pool 7 (collocations empty excluded, examples valid).
        self.assertEqual(report["legacy_valid_pool"], 7)
        self.assertEqual(report["unjustified_nullification_rate"], 1 / 7)
        self.assertEqual(report["regression_rate"], 1 / 7)
        self.assertEqual(report["nullification_rate"], 1 / 7)
        self.assertEqual(report["justified_change_rate"], 0 / 7)

    def test_pool_boundary_null_vs_defective(self):
        seed = self._seed()
        cand = {k: v for k, v in seed.items()}
        cand["mnemonic_ar"] = "Say it like a firm no: ref-use"
        report = seed_preservation_report(seed, cand, LEMMA)
        self.assertIsNotNone(report["preservation_precision"])
        self.assertEqual(report["legacy_defective_pool"], 1)
        self.assertEqual(report["repair_recall"], 1 / 1)

    def test_missing_target_in_candidate_examples_regression(self):
        seed = self._seed()
        cand = {k: v for k, v in seed.items()}
        cand["examples"] = ["They said no", "She said no twice",
                            "He said no quietly"]
        report = seed_preservation_report(seed, cand, LEMMA)
        self.assertEqual(report["fields"]["examples"]["category"],
                         "regression")

    def test_mnemonic_cursor_key_not_misread_as_null(self):
        # Regression guard: the generator passes the classifier cursor
        # (key "mnemonic"); the blind arm uses "mnemonic_ar". A real
        # non-null rewrite must be "changed", never null-regression.
        seed = self._seed()
        seed["mnemonic"] = "legacy hook linking refuse to reuse"
        cand = {k: v for k, v in seed.items() if k != "mnemonic"}
        cand["mnemonic"] = "firm refusal hook: reuse the R"
        report = seed_preservation_report(
            seed, cand, LEMMA,
            field_decisions={"mnemonic": {"action": "improve",
                                          "reason": "clearer hook",
                                          "replacement_superiority": True}})
        self.assertEqual(report["fields"]["mnemonic"]["category"],
                         "changed")

    def test_mnemonic_arm_key_alias(self):
        seed = self._seed()
        seed["mnemonic"] = "legacy hook linking refuse to reuse"
        cand = {k: v for k, v in seed.items() if k != "mnemonic"}
        cand["mnemonic_ar"] = "firm refusal hook: reuse the R"
        report = seed_preservation_report(
            seed, cand, LEMMA,
            field_decisions={"mnemonic": {"action": "improve",
                                          "reason": "clearer hook",
                                          "replacement_superiority": True}})
        self.assertEqual(report["fields"]["mnemonic"]["category"],
                         "changed")


if __name__ == "__main__":
    unittest.main()