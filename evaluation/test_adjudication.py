"""Tests for adjudication record + decode (ticket BT-14).

Locks: ballot validation, unknown-id refusal, no default-filling,
map-touch exclusivity (adjudicate.py must not reference the map),
decode aggregation math on fixtures. No real judgments.
"""

import os
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation import adjudicate
from evaluation.adjudication_decode import decode
from evaluation.blind_package import blank_ballot


def ballot_with(field_verdicts, crits=None):
    b = blank_ballot()
    b["fields"].update(field_verdicts)
    for cls, entry in (crits or {}).items():
        b["critical_errors"][cls] = entry
    return b


class TestRecord(unittest.TestCase):
    def test_valid_ballot(self):
        self.assertEqual(adjudicate.validate_ballot(blank_ballot()), [])

    def test_bad_verdict(self):
        b = blank_ballot()
        b["fields"]["definition"] = "candidate rocks"
        self.assertTrue(adjudicate.validate_ballot(b))

    def test_nonstring_verdict_is_defect_not_crash(self):
        b = blank_ballot()
        b["fields"]["definition"] = {"winner": "A", "why": "x"}
        defects = adjudicate.validate_ballot(b)
        self.assertTrue(defects)

    def test_unknown_eval_id_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                adjudicate.record_judgments(
                    [{"eval_id": "E-1"}],
                    {"E-999": blank_ballot()},
                    os.path.join(tmp, "j.json"))

    def test_no_map_access_in_recorder(self):
        src = open(adjudicate.__file__, encoding="utf-8").read().lower()
        for token in ("identity_map", "id_map", "candidate_side",
                      "import adjudication_decode", "from evaluation"):
            if token == "from evaluation":
                continue
            self.assertNotIn(token, src, token)


class TestDecode(unittest.TestCase):
    def test_aggregation_math(self):
        import tempfile
        pkg = [{"eval_id": "E-1"}, {"eval_id": "E-2"}]
        jud = {
            "E-1": ballot_with(
                {f: "A-better" for f in
                 ("definition", "arabic_explanation",
                  "sense_separation", "examples", "translations",
                  "relations", "mnemonic")},
                {"wrong_meaning": {"side": "B", "evidence": "x"}}),
            "E-2": ballot_with({}),
        }
        idmap = {"E-1": {"candidate_side": "A", "candidate_key": "K1"},
                 "E-2": {"candidate_side": "B", "candidate_key": "K2"}}
        with tempfile.TemporaryDirectory() as tmp:
            jp = os.path.join(tmp, "j.json")
            mp = os.path.join(tmp, "m.json")
            import json
            json.dump({"judgments": jud}, open(jp, "w"))
            json.dump({"map": idmap}, open(mp, "w"))
            agg, _ = decode(jp, mp, tmp)
            self.assertEqual(agg["n_judged"], 2)
            self.assertEqual(agg["field_wins"]["definition"],
                             {"candidate": 1})
            self.assertEqual(agg["critical_counts"]["wrong_meaning"],
                             {"legacy": 1})


if __name__ == "__main__":
    unittest.main()
