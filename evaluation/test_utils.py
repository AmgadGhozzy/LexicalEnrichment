import unittest
import os
import tempfile

from evaluation.utils import (
    canonical_hash, get_file_hash, hash_file_bytes, sha256_string,
    load_file, write_file, load_json, write_json, generate_experiment_id,
)

class TestHashing(unittest.TestCase):

    def test_identical_bytes_identical_hash(self):
        content = b"hello world\n"
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            path = f.name
        try:
            self.assertEqual(get_file_hash(path), hash_file_bytes(path))
            self.assertEqual(get_file_hash(path), hash_file_bytes(path))
        finally:
            os.remove(path)

    def test_different_bytes_different_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"aaa")
            a_path = f.name
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"aab")
            b_path = f.name
        try:
            self.assertNotEqual(get_file_hash(a_path), get_file_hash(b_path))
        finally:
            os.remove(a_path)
            os.remove(b_path)

    def test_missing_file_returns_none(self):
        self.assertIsNone(get_file_hash("/nonexistent/definitely-missing.json"))

    def test_missing_file_hash_file_bytes_raises(self):
        with self.assertRaises(FileNotFoundError):
            hash_file_bytes("/nonexistent/definitely-missing.json")

    def test_sha256_string_matches_manual(self):
        import hashlib
        s = "some string \u0645\u0646\u0635"
        expected = hashlib.sha256(s.encode('utf-8')).hexdigest()
        self.assertEqual(sha256_string(s), expected)


class TestCanonicalHash(unittest.TestCase):

    def test_identical_dicts_canonical_identical(self):
        a = {"b": 1, "a": [1, 2, {"z": "x"}]}
        b = {"a": [1, 2, {"z": "x"}], "b": 1}
        self.assertEqual(canonical_hash(a), canonical_hash(b))

    def test_key_order_does_not_matter(self):
        d1 = {"x": 1, "y": 2}
        d2 = {"y": 2, "x": 1}
        self.assertEqual(canonical_hash(d1), canonical_hash(d2))

    def test_list_order_matters(self):
        l1 = [1, 2, 3]
        l2 = [3, 2, 1]
        self.assertNotEqual(canonical_hash(l1), canonical_hash(l2))

    def test_string_hashed_as_raw_utf8(self):
        import hashlib
        s = "\u0645\u0646\u0635"
        self.assertEqual(canonical_hash(s), hashlib.sha256(s.encode('utf-8')).hexdigest())


class TestFileIO(unittest.TestCase):

    def test_roundtrip_text_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sample.txt")
            write_file(path, "hello \u0645\u0631\u062d\u0628\u0627")
            self.assertEqual(load_file(path), "hello \u0645\u0631\u062d\u0628\u0627")

    def test_roundtrip_json_file(self):
        data = {"a": [1, 2], "\u062a": "value"}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sample.json")
            write_json(path, data)
            self.assertEqual(load_json(path), data)


class TestExperimentId(unittest.TestCase):

    def test_id_format(self):
        import re
        import datetime
        exp_id = generate_experiment_id(prefix="EXP")
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        self.assertRegex(exp_id, rf"^EXP-{re.escape(today)}-\d{{3}}$")


if __name__ == "__main__":
    unittest.main()
