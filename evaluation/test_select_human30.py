"""Tests for evaluation.select_human30 stratified sampler."""

import copy
import json
import os
import tempfile

import pytest

from evaluation import select_human30 as s
from evaluation.blind_package import FIELDS


def synthetic_classified():
    """Deterministic synthetic 100-card corpus with known pools."""
    classified = {}

    def c(eid, key, elig, focus):
        return {"key": key, "eligibility": elig, "focus": focus}

    # relations corpus (30) with forced this/det and fish/noun
    for i in range(30):
        eid = "r-%03d" % i
        tag = ("legacy_preserved" if i % 2 == 0
               else "emptied")
        classified[eid] = c(eid, "rel/%d" % i,
                            {"relations": ["candidate", tag]},
                            ["relations"])
    classified["r-000"] = c("r-000", "this/det",
                            {"relations": ["candidate", "emptied"]},
                            ["relations"])
    classified["r-001"] = c("r-001", "fish/noun",
                            {"relations": ["candidate",
                                           "legacy_preserved"]},
                            ["relations"])
    # translations (40): candidate-changed / candidate-preserved /
    # legacy / tie
    verdicts = (["candidate"] * 12 + ["candidate"] * 8 + ["legacy"] * 8
                + ["tie"] * 12)
    srcs = (["changed"] * 12 + ["preserved"] * 8 + ["changed"] * 8
            + ["changed"] * 12)
    for i, (v, src) in enumerate(zip(verdicts, srcs)):
        eid = "t-%03d" % i
        classified[eid] = c(eid, "trans/%d" % i,
                            {"translations": [v, src]},
                            ["translations"])
    # sense separation (20): multi_pos then abstain
    for i in range(20):
        eid = "s-%03d" % i
        tag = "abstain" if i >= 8 else "multi_pos"
        classified[eid] = c(eid, "sense/%d" % i,
                            {"sense_separation": [tag]},
                            ["sense_separation"])
    # examples (20): candidate / legacy + critical_related markers
    for i in range(20):
        eid = "e-%03d" % i
        tags = ["candidate" if i < 10 else "legacy"]
        if i % 5 == 0:
            tags.append("critical_related")
        classified[eid] = c(eid, "ex/%d" % i, {"examples": tags},
                            ["examples"])
    # definition/arabic (10) with forced billion/num
    for i in range(10):
        eid = "d-%03d" % i
        classified[eid] = c(eid, "def/%d" % i,
                            {"definition_arabic": ["semantic_change",
                                                   "candidate"]},
                            ["definition_arabic"])
    classified["d-000"] = c("d-000", "billion/num",
                            {"definition_arabic": ["semantic_change",
                                                   "candidate"]},
                            ["definition_arabic"])
    # mnemonic (10)
    for i in range(10):
        eid = "m-%03d" % i
        tags = ["changed"]
        if i % 2 == 1:
            tags.append("indirect")
        classified[eid] = c(eid, "mn/%d" % i, {"mnemonic": tags},
                            ["mnemonic"])
    return classified


def test_strata_counts_match_spec():
    sel = s.select_cards(synthetic_classified())
    counts = {}
    for x in sel:
        counts[x["stratum"]] = counts.get(x["stratum"], 0) + 1
    assert counts == dict(s.STRATA)


def test_thirty_unique_ids():
    sel = s.select_cards(synthetic_classified())
    ids = [x["eval_id"] for x in sel]
    assert len(ids) == 30
    assert len(set(ids)) == 30


def test_forced_cases_included():
    sel = s.select_cards(synthetic_classified())
    ids = {x["eval_id"] for x in sel}
    assert {"r-000", "r-001", "d-000"} <= ids


def test_translations_stratum_covers_all_verdicts():
    sel = s.select_cards(synthetic_classified())
    t = {x["eval_id"] for x in sel if x["stratum"] == "translations"}
    assert len(t) == 10
    verdicts = {synthetic_classified()[e]["eligibility"]
                ["translations"][0] for e in t}
    assert verdicts >= {"candidate", "legacy", "tie"}


def test_relations_stratum_has_no_wrong_stratum_cards():
    sel = s.select_cards(synthetic_classified())
    rel_keys = {synthetic_classified()[x["eval_id"]]["key"]
                for x in sel if x["stratum"] == "relations"}
    assert "this/det" in rel_keys and "fish/noun" in rel_keys
    assert len(rel_keys) == 6


def test_deterministic_selection():
    a = s.select_cards(synthetic_classified())
    b = s.select_cards(synthetic_classified())
    assert a == b


def test_seed_changes_selection():
    a = s.select_cards(synthetic_classified())
    b = s.select_cards(synthetic_classified(), seed=1)
    assert a != b


def test_insufficient_pool_raises():
    classified = copy.deepcopy(synthetic_classified())
    # shrink the whole translations pool far below its quota of 10
    kept = 0
    for info in classified.values():
        if "translations" in info["eligibility"]:
            if kept < 3:
                info["eligibility"]["translations"] = ["candidate"]
                kept += 1
            else:
                del info["eligibility"]["translations"]

    with pytest.raises(RuntimeError):
        s.select_cards(classified, seed=99)


def test_synthetic_has_enough_pools():
    classified = synthetic_classified()
    for stratum, quota in s.STRATA:
        n = sum(1 for info in classified.values()
                if stratum in info["eligibility"])
        assert n >= quota, (stratum, n, quota)


def test_ballot_template_blank():
    sel = s.select_cards(synthetic_classified())
    with tempfile.TemporaryDirectory() as tmp:
        path = s.write_ballot_template(sel, os.path.join(tmp, "b.json"))
        data = json.load(open(path, encoding="utf-8"))
    assert len(data["judgments"]) == 30
    for j in data["judgments"].values():
        assert sorted(j["fields"].keys()) == sorted(FIELDS)
        assert j["fields"]["definition"] == "unjudged"
        assert all(v == "unjudged" for v in j["fields"].values())


def test_no_cross_stratum_reuse_in_selection():
    sel = s.select_cards(synthetic_classified())
    ids = [x["eval_id"] for x in sel]
    assert len(ids) == len(set(ids))