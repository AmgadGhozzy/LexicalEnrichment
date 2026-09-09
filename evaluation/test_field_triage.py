"""Unit tests for the deterministic triage engine (Ticket 17, rules v0.1).

Every rule has a pass-fixture and a fail-fixture. No DB, no network, no LLM.
"""

import json
import unittest

from evaluation.field_triage import (
    QUOTAS,
    QUOTA_EXEMPT,
    QuotaBreach,
    _canon_json,
    build_sample,
    check_quotas_or_halt,
    lemma_form_closure,
    quota_report,
    target_present,
    triage_card,
)


def _row(**kw):
    base = {"id": 1, "wordEn": "abandon", "pos": "verb", "primarySense": "Action",
            "definitionEn": "To leave a place or person completely.",
            "definitionAr": "يترك المكان تمامًا.",
            "examples": json.dumps({"A1": "Do not abandon your friends.",
                                    "B1": "They had to abandon the sinking ship."}),
            "arabicAr": "يترك / يتخلى عن",
            "mnemonicAr": None,
            "synonyms": json.dumps(["leave", "desert"]),
            "antonyms": json.dumps(["stay"]),
            "collocations": json.dumps(["abandon ship", "abandon hope"])}
    base.update(kw)
    return base


def _rec(records, field):
    return [r for r in records if r["field"] == field][0]


class TestTargetPresent(unittest.TestCase):
    def test_exact_token(self):
        self.assertTrue(target_present("Do not abandon your friends.", "abandon", "verb"))

    def test_missing_token(self):
        self.assertFalse(target_present("Do not leave your friends.", "abandon", "verb"))

    def test_multiword_phrase(self):
        self.assertTrue(target_present("I like chocolate ice cream.", "ice cream", "noun"))

    def test_hyphenated_phrase(self):
        self.assertTrue(target_present("Please line up here.", "line-up", "verb"))

    def test_regular_ed_phrase(self):
        self.assertTrue(target_present("Cars lined up for the ferry.", "line-up", "verb"))

    def test_irregular_not_matched_documented_residue(self):
        # drank-class stays a HARD signal by C1 decision: no irregular guessing.
        self.assertFalse(target_present("She drank a glass of milk.", "drink", "verb"))


class TestClosureC1(unittest.TestCase):
    def test_noun_plural(self):
        self.assertIn("cars", lemma_form_closure("car", "noun"))

    def test_noun_ies(self):
        self.assertIn("universities", lemma_form_closure("university", "noun"))

    def test_noun_has_no_verbal_ed(self):
        # POS gating: car/noun must NOT generate "cared" (a different word).
        self.assertNotIn("cared", lemma_form_closure("car", "noun"))

    def test_noun_es_only_after_sibilant(self):
        self.assertNotIn("cares", lemma_form_closure("car", "noun"))
        self.assertIn("boxes", lemma_form_closure("box", "noun"))

    def test_verb_s_and_ed_and_ing(self):
        forms = lemma_form_closure("last", "verb")
        self.assertTrue({"lasts", "lasted", "lasting"} <= forms)

    def test_verb_edrop_ing(self):
        forms = lemma_form_closure("make", "verb")
        self.assertIn("making", forms)
        self.assertNotIn("makeing", forms)

    def test_verb_doubling(self):
        self.assertIn("stopped", lemma_form_closure("stop", "verb"))

    def test_adj_comparative(self):
        self.assertIn("longer", lemma_form_closure("long", "adv"))
        self.assertIn("bigger", lemma_form_closure("big", "adj"))

    def test_closed_pos_base_only(self):
        self.assertEqual(lemma_form_closure("over", "prep"), frozenset({"over"}))

    def test_plural_keep_end_to_end(self):
        row = _row(wordEn="car", pos="noun",
                   examples=json.dumps({"A1": "He collects vintage classic cars."}))
        r = [x for x in triage_card(row) if x["field"] == "examples"][0]
        self.assertEqual(r["triage_status"], "KEEP")

    def test_irregular_hard_end_to_end(self):
        row = _row(wordEn="drink", pos="verb",
                   examples=json.dumps({"A1": "She drank a glass of milk."}))
        r = [x for x in triage_card(row) if x["field"] == "examples"][0]
        self.assertEqual(r["defect_code"], "EX_NO_LEMMA_TOKEN")


class TestExamples(unittest.TestCase):
    def test_clean_keep(self):
        r = _rec(triage_card(_row()), "examples")
        self.assertEqual(r["triage_status"], "KEEP")
        self.assertIsNone(r["defect_code"])

    def test_missing_lemma_hard(self):
        row = _row(examples=json.dumps({"A1": "Do not leave your friends."}))
        r = _rec(triage_card(row), "examples")
        self.assertEqual(r["triage_status"], "LLM_REVIEW")
        self.assertEqual(r["defect_code"], "EX_NO_LEMMA_TOKEN")
        self.assertEqual(r["evidence"]["failing_bands"], ["A1"])

    def test_malformed_json(self):
        r = _rec(triage_card(_row(examples="{not json")), "examples")
        self.assertEqual(r["defect_code"], "EX_MALFORMED_JSON")

    def test_empty_band(self):
        row = _row(examples=json.dumps({"A1": "Do not abandon ship.", "B1": "  "}))
        r = _rec(triage_card(row), "examples")
        self.assertEqual(r["defect_code"], "EX_EMPTY_BAND")

    def test_duplicate_bands(self):
        s = "Do not abandon your friends."
        row = _row(examples=json.dumps({"A1": s, "B1": s}))
        r = _rec(triage_card(row), "examples")
        self.assertEqual(r["defect_code"], "EX_DUPLICATE_BANDS")

    def test_single_soft_signal_keep_with_evidence(self):
        row = _row(examples=json.dumps({"A1": "Do not abandon your friends"}))
        r = _rec(triage_card(row), "examples")
        self.assertEqual(r["triage_status"], "KEEP")
        self.assertIn("soft_signals", r["evidence"])

    def test_two_soft_types_escalate(self):
        row = _row(examples=json.dumps({"A1": "do not abandon your friends"}))
        r = _rec(triage_card(row), "examples")
        self.assertEqual(r["triage_status"], "LLM_REVIEW")
        self.assertEqual(r["defect_code"], "EX_SOFT_ESCALATION")
        self.assertTrue(r["requires_llm"])

    def test_array_format_keep(self):
        row = _row(wordEn="event", pos="noun", examples=json.dumps(
            ["It was a big event.", "The party is a fun event."]))
        r = _rec(triage_card(row), "examples")
        self.assertEqual(r["triage_status"], "KEEP")
        self.assertEqual(r["evidence"]["format"], "array")

    def test_array_format_missing_lemma(self):
        row = _row(wordEn="event", pos="noun", examples=json.dumps(
            ["It was a big party.", "The party is fun."]))
        r = _rec(triage_card(row), "examples")
        self.assertEqual(r["defect_code"], "EX_NO_LEMMA_TOKEN")
        self.assertEqual(r["evidence"]["format"], "array")

    def test_array_format_non_string_malformed(self):
        row = _row(examples=json.dumps(["Fine abandon ship.", 7]))
        r = _rec(triage_card(row), "examples")
        self.assertEqual(r["defect_code"], "EX_MALFORMED_JSON")


class TestDefinitionArabic(unittest.TestCase):
    def test_definition_empty(self):
        r = _rec(triage_card(_row(definitionEn="  ")), "definition_en")
        self.assertEqual((r["triage_status"], r["defect_code"]),
                         ("LLM_REVIEW", "DEF_EMPTY"))

    def test_definition_circular(self):
        r = _rec(triage_card(_row(definitionEn="To abandon")), "definition_en")
        self.assertEqual(r["defect_code"], "DEF_CIRCULAR")

    def test_definition_generic(self):
        r = _rec(triage_card(_row(definitionEn="none")), "definition_en")
        self.assertEqual(r["defect_code"], "DEF_GENERIC_NULL")

    def test_arabic_empty(self):
        r = _rec(triage_card(_row(definitionAr="")), "explanation_ar")
        self.assertEqual(r["defect_code"], "AR_EMPTY")

    def test_arabic_generic(self):
        r = _rec(triage_card(_row(definitionAr="لا يوجد")), "explanation_ar")
        self.assertEqual(r["defect_code"], "AR_GENERIC_NULL")

    def test_arabic_no_script(self):
        r = _rec(triage_card(_row(definitionAr="this is english only")), "explanation_ar")
        self.assertEqual(r["defect_code"], "AR_NO_ARABIC_SCRIPT")


class TestTranslationsMnemonic(unittest.TestCase):
    def test_translations_empty(self):
        r = _rec(triage_card(_row(arabicAr="  ")), "translations")
        self.assertEqual(r["defect_code"], "TR_EMPTY")

    def test_translations_duplicates(self):
        r = _rec(triage_card(_row(arabicAr="يترك / يترك")), "translations")
        self.assertEqual(r["defect_code"], "TR_DUPLICATE_SLOTS")

    def test_translations_no_arabic_soft_keep(self):
        r = _rec(triage_card(_row(arabicAr="leave / desert")), "translations")
        self.assertEqual(r["triage_status"], "KEEP")
        self.assertIn("soft_signals", r["evidence"])

    def test_mnemonic_null_valid(self):
        r = _rec(triage_card(_row(mnemonicAr=None)), "mnemonic")
        self.assertEqual(r["triage_status"], "KEEP")
        self.assertTrue(r["evidence"]["null_valid"])

    def test_mnemonic_empty_repair(self):
        r = _rec(triage_card(_row(mnemonicAr="")), "mnemonic")
        self.assertEqual((r["triage_status"], r["defect_code"]),
                         ("DETERMINISTIC_REPAIR", "MNE_EMPTY_STRING"))
        self.assertFalse(r["requires_llm"])

    def test_mnemonic_generic_repair(self):
        r = _rec(triage_card(_row(mnemonicAr="لا يوجد")), "mnemonic")
        self.assertEqual((r["triage_status"], r["defect_code"]),
                         ("DETERMINISTIC_REPAIR", "MNE_GENERIC_NULL"))

    def test_mnemonic_bad_type_manual(self):
        r = _rec(triage_card(_row(mnemonicAr=123)), "mnemonic")
        self.assertEqual((r["triage_status"], r["requires_human"]),
                         ("MANUAL_REVIEW", True))


class TestRelations(unittest.TestCase):
    def test_self_reference(self):
        row = _row(synonyms=json.dumps(["abandon", "leave"]))
        r = _rec(triage_card(row), "relations_synonyms")
        self.assertEqual(r["defect_code"], "REL_SELF_REFERENCE")

    def test_duplicates(self):
        row = _row(antonyms=json.dumps(["Stay", "stay"]))
        r = _rec(triage_card(row), "relations_antonyms")
        self.assertEqual(r["defect_code"], "REL_DUPLICATES")

    def test_syn_ant_overlap_flags_both(self):
        row = _row(synonyms=json.dumps(["leave"]), antonyms=json.dumps(["Leave"]))
        rs = _rec(triage_card(row), "relations_synonyms")
        ra = _rec(triage_card(row), "relations_antonyms")
        self.assertEqual(rs["defect_code"], "REL_SYN_ANT_OVERLAP")
        self.assertEqual(ra["defect_code"], "REL_SYN_ANT_OVERLAP")

    def test_empty_list_is_not_a_defect(self):
        row = _row(synonyms=json.dumps([]))
        r = _rec(triage_card(row), "relations_synonyms")
        self.assertEqual(r["triage_status"], "KEEP")
        self.assertTrue(r["evidence"]["inventory_empty"])

    def test_null_is_not_a_defect(self):
        row = _row(antonyms=None)
        r = _rec(triage_card(row), "relations_antonyms")
        self.assertEqual(r["triage_status"], "KEEP")
        self.assertTrue(r["evidence"]["inventory_null"])

    def test_malformed(self):
        row = _row(collocations="[oops")
        r = _rec(triage_card(row), "relations_collocations")
        self.assertEqual(r["defect_code"], "REL_MALFORMED_JSON")

    def test_non_string_item(self):
        row = _row(synonyms=json.dumps(["leave", 7]))
        r = _rec(triage_card(row), "relations_synonyms")
        self.assertEqual(r["defect_code"], "REL_INVALID_ITEM")

    def test_collocation_without_lemma_soft_keep(self):
        row = _row(collocations=json.dumps(["great speakers", "abandon hope"]))
        r = _rec(triage_card(row), "relations_collocations")
        self.assertEqual(r["triage_status"], "KEEP")
        self.assertIn("soft_signals", r["evidence"])


class TestSenseAndSchema(unittest.TestCase):
    def test_sense_default_manual(self):
        r = _rec(triage_card(_row()), "sense_separation")
        self.assertEqual(r["triage_status"], "MANUAL_REVIEW")
        self.assertIsNone(r["defect_code"])
        self.assertTrue(r["requires_human"])
        self.assertFalse(r["requires_llm"])

    def test_record_schema_keys(self):
        for r in triage_card(_row()):
            self.assertEqual(sorted(r.keys()),
                             ["current_value_hash", "defect_code", "evidence", "field",
                              "identity", "requires_human", "requires_llm", "triage_status"])
            self.assertTrue(r["current_value_hash"].startswith("sha256:"))

    def test_nine_records_per_card(self):
        self.assertEqual(len(triage_card(_row())), 9)

    def test_determinism(self):
        a = _canon_json(triage_card(_row()))
        b = _canon_json(triage_card(_row()))
        self.assertEqual(a, b)


class TestQuotas(unittest.TestCase):
    def _flagged(self, field, n, status="LLM_REVIEW"):
        return [{"identity": {"id": i, "lemma": "w", "pos": "noun"}, "field": field,
                 "current_value_hash": "sha256:x", "triage_status": status,
                 "defect_code": "X", "evidence": {}, "requires_llm": True,
                 "requires_human": False} for i in range(n)]

    def _kept(self, field, n):
        recs = self._flagged(field, n)
        for r in recs:
            r["triage_status"] = "KEEP"
            r["defect_code"] = None
            r["requires_llm"] = False
        return recs

    def test_breach_halts(self):
        recs = self._flagged("examples", 36) + self._kept("examples", 64)
        with self.assertRaises(QuotaBreach) as ctx:
            check_quotas_or_halt(recs)
        self.assertIn("examples", ctx.exception.report["breached"])

    def test_under_quota_passes(self):
        recs = self._flagged("definition_en", 19) + self._kept("definition_en", 81)
        report = check_quotas_or_halt(recs)
        self.assertFalse(report["halted"])

    def test_sense_exempt_from_quotas(self):
        recs = self._flagged("sense_separation", 100, status="MANUAL_REVIEW")
        report = quota_report(recs)
        self.assertEqual(report["per_field"], {})
        self.assertFalse(report["halted"])

    def test_quota_values_match_ticket(self):
        self.assertEqual(QUOTAS["examples"], 0.35)
        self.assertEqual(QUOTAS["translations"], 0.30)
        self.assertEqual(QUOTAS["definition_en"], 0.20)
        self.assertIn("sense_separation", QUOTA_EXEMPT)


class TestBuildSample(unittest.TestCase):
    def test_sample_deterministic_and_sized(self):
        import json
        import sqlite3
        man = json.load(open(
            ".scratch/lexical-migration-build/output/migration_readiness/"
            "migration_manifest_348.json", encoding="utf-8"))
        wave1 = frozenset(r["wordsMaster_id"] for r in man["records"])
        con = sqlite3.connect("file:WordsMaster.db?mode=ro", uri=True)
        try:
            a = build_sample(con, n=300, wave1_ids=wave1)
            b = build_sample(con, n=300, wave1_ids=wave1)
        finally:
            con.close()
        self.assertEqual(a["ids"], b["ids"])
        self.assertEqual(len(a["ids"]), 300)
        for name, q in a["representation"].items():
            self.assertGreaterEqual(q["have"], q["need"], name)


if __name__ == "__main__":
    unittest.main()
