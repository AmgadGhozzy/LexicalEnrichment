"""Tests for LLM-versioning instrumentation (build ticket 05).

Locks spec section 4 / wayfinding 11: completeness, append-only
history, input-hash capture. No DB, no network; tmp dirs only.
"""

import os
import sys
import tempfile
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.run_provenance import (
    REQUIRED_DIMENSIONS,
    append_history,
    build_generation_record,
    read_history,
    verify_record,
)
from evaluation.utils import canonical_hash


def v223_dims(output):
    return {
        "prompt": {
            "prompt_id": "lexical_enrichment_final_m3",
            "prompt_version": "2.2.3",
        },
        "schema": {
            "schema_id": "lexical_output",
            "schema_version": "v1.1-candidate",
        },
        "model": {
            "provider": "google",
            "model_id": "gemini-3.8-flash",
            "model_version": "gemini-3.8-flash",
        },
        "generation_config": {"temperature": 1.0},
        "reasoning_grounding": {
            "thinking_mode": "low",
            "grounding_mode": "off",
        },
        "run": {
            "experiment_id": "EXP-TEST",
            "run_id": "RUN-1",
            "input_snapshot_id": "golden_v2",
            "input_snapshot_hash": "2a179128",
        },
        "integrity": {
            "output_hash": canonical_hash(output),
            "status": "ok",
        },
    }


class TestCompleteness(unittest.TestCase):
    def test_full_record_builds(self):
        rec = build_generation_record({"w": 1}, **v223_dims({"w": 1}))
        self.assertEqual(verify_record(rec, {"w": 1}), [])
        self.assertEqual(set(rec.keys()) - {"version"}, set(REQUIRED_DIMENSIONS))

    def test_each_group_omitted_fails(self):
        base = v223_dims({"w": 1})
        for group in REQUIRED_DIMENSIONS:
            dims = {k: dict(v) for k, v in base.items()}
            del dims[group]
            with self.assertRaises(ValueError, msg=group):
                build_generation_record({"w": 1}, **dims)

    def test_each_field_omitted_fails(self):
        base = v223_dims({"w": 1})
        for group, fields in REQUIRED_DIMENSIONS.items():
            for field in fields:
                if group == "run" and field == "generated_at":
                    continue  # defaulted, tested separately
                dims = {k: dict(v) for k, v in base.items()}
                del dims[group][field]
                with self.assertRaises(ValueError, msg="%s.%s" % (group, field)):
                    build_generation_record({"w": 1}, **dims)

    def test_generated_at_defaulted(self):
        dims = v223_dims({"w": 1})
        self.assertNotIn("generated_at", dims["run"])
        rec = build_generation_record({"w": 1}, **dims)
        self.assertTrue(rec["run"]["generated_at"])

    def test_output_hash_mismatch_refused(self):
        dims = v223_dims({"w": 1})
        dims["integrity"]["output_hash"] = "deadbeef"
        with self.assertRaises(ValueError):
            build_generation_record({"w": 1}, **dims)

    def test_bad_status_refused(self):
        dims = v223_dims({"w": 1})
        dims["integrity"]["status"] = "maybe"
        with self.assertRaises(ValueError):
            build_generation_record({"w": 1}, **dims)

    def test_verify_catches_stale_cache(self):
        rec = build_generation_record({"w": 1}, **v223_dims({"w": 1}))
        self.assertIn("output_hash mismatch", verify_record(rec, {"w": 2}))


class TestAppendOnly(unittest.TestCase):
    def test_append_then_reread(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "history.jsonl")
            out1, out2 = {"w": 1}, {"w": 2}
            d1 = v223_dims(out1)
            d2 = v223_dims(out2)
            d2["run"]["run_id"] = "RUN-2"
            self.assertEqual(
                append_history(path, build_generation_record(out1, **d1)), 1
            )
            self.assertEqual(
                append_history(path, build_generation_record(out2, **d2)), 2
            )
            rows = read_history(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["run"]["run_id"], "RUN-1")
            self.assertEqual(rows[1]["run"]["run_id"], "RUN-2")

    def test_no_update_api_exists(self):
        import evaluation.run_provenance as rp

        for name in ("update", "delete", "overwrite", "replace", "upsert"):
            self.assertFalse(
                hasattr(rp, name), "append-only violation: %s" % name
            )

    def test_defective_record_never_appended(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "history.jsonl")
            with self.assertRaises(ValueError):
                append_history(path, {"version": 1})
            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
