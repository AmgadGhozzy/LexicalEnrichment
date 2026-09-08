"""Tests for evidence + quarantine schemas (ticket 07).

Locks spec sections 2, 3, 6: additive structures, append-only
provenance, derived-only is_ielts VIEW, quarantine/identity ID
separation. In-memory SQLite only; no repo database touched.
"""

import os
import sqlite3
import sys
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import evaluation.evidence_schema as es


def memdb():
    conn = sqlite3.connect(":memory:")
    es.create_schema(conn)
    return conn


class TestStructure(unittest.TestCase):
    def test_tables_and_view_exist(self):
        conn = memdb()
        names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        }
        for t in (
            "lexical_identity",
            "source_snapshot",
            "lexical_frequency",
            "cefr_evidence",
            "ielts_evidence",
            "quarantine_record",
            "mapping_provenance",
            "is_ielts",
        ):
            self.assertIn(t, names, t)

    def test_idempotent_create(self):
        conn = memdb()
        es.create_schema(conn)  # must not raise

    def test_no_update_delete_helpers(self):
        for name in ("update", "delete", "overwrite", "replace", "upsert",
                     "remove", "drop"):
            self.assertFalse(hasattr(es, name), name)

    def test_pos_enum_enforced(self):
        conn = memdb()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO lexical_identity VALUES ('get','noun+verb')"
            )

    def test_fk_enforced(self):
        conn = memdb()
        with self.assertRaises(sqlite3.IntegrityError):
            es.add_frequency(conn, "ghost", "noun", "v1", "en", 5.0, "t")


class TestInvariants(unittest.TestCase):
    def test_is_ielts_derived_only(self):
        conn = memdb()
        es.add_identity(conn, "adopt", "verb")
        es.add_ielts_evidence(conn, "adopt", "verb", 2, "adopt", "verb",
                              "t", topic="Growing up")
        got = conn.execute("SELECT * FROM is_ielts").fetchall()
        self.assertEqual(got, [("adopt", "verb", 1)])
        # unapproved rows never set the flag
        es.add_identity(conn, "trust", "verb")
        es.add_ielts_evidence(conn, "trust", "verb", 34, "trust", "noun",
                              "t", approved=0)
        got = {r[:2] for r in conn.execute("SELECT * FROM is_ielts")}
        self.assertNotIn(("trust", "verb"), got)
        # the view is not writable: no independent write path exists
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute(
                "INSERT INTO is_ielts VALUES ('x','noun',1)")

    def test_many_topics_one_identity(self):
        conn = memdb()
        es.add_identity(conn, "adopt", "verb")
        es.add_ielts_evidence(conn, "adopt", "verb", 2, "adopt", "verb",
                              "t", topic="Growing up")
        es.add_ielts_evidence(conn, "adopt", "verb", 9, "adopt", "verb",
                              "t", topic="Family")
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM is_ielts").fetchone()[0], 1)
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM ielts_evidence").fetchone()[0], 2)

    def test_quarantine_id_is_not_identity_id(self):
        conn = memdb()
        es.add_quarantine(conn, "multiword", "solar system",
                          "solar system", "IeltsWord.db", "MULTIWORD", "t")
        rid = conn.execute(
            "SELECT record_id FROM quarantine_record").fetchone()[0]
        idents = conn.execute("SELECT * FROM lexical_identity").fetchall()
        self.assertEqual(idents, [])
        self.assertIsInstance(rid, int)

    def test_snapshot_immutable(self):
        conn = memdb()
        es.register_snapshot(conn, "S1", "WordsMaster.db", "abc", "t",
                             source_rows=7300)
        with self.assertRaises(sqlite3.IntegrityError):
            es.register_snapshot(conn, "S1", "WordsMaster.db", "xyz", "t")

    def test_mapping_classification_closed_set(self):
        conn = memdb()
        with self.assertRaises(sqlite3.IntegrityError):
            es.add_mapping_provenance(conn, 1, "x", "x", "noun",
                                      "MAYBE", "t")


if __name__ == "__main__":
    unittest.main()
