import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch

from evaluation.utils import EXPERIMENTS_DIR, load_json
from evaluation.batch_input_builder import build_batch_input
from evaluation.batch_importer import import_batch_output

class TestBatchInfrastructure(unittest.TestCase):
    
    def test_input_builder_determinism(self):
        exp_id = "EXP-TEST-BATCH"
        exp_dir = os.path.join(EXPERIMENTS_DIR, exp_id)
        if os.path.exists(exp_dir):
            shutil.rmtree(exp_dir)
            
        file1, hash1 = build_batch_input("gemini_flash_v1.1_batch_pilot.json", exp_id)
        file2, hash2 = build_batch_input("gemini_flash_v1.1_batch_pilot.json", exp_id)
        
        self.assertEqual(hash1, hash2)
        
        with open(file1, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        self.assertEqual(len(lines), 160)
        cand_ids = set()
        for line in lines:
            record = json.loads(line)
            cand_ids.add(record["key"])
            self.assertIn("request", record, "request must be present")
            
        self.assertEqual(len(cand_ids), 160)
        shutil.rmtree(exp_dir)
            
    @patch('evaluation.batch_importer.EXPERIMENTS_DIR', new_callable=lambda: tempfile.mkdtemp())
    @patch('evaluation.batch_importer.GOLDEN_SET_DIR', new_callable=lambda: tempfile.mkdtemp())
    def test_importer_strict_mapping(self, mock_golden_dir, mock_exp_dir):
        # Create fake golden set
        golden_data = [{"id": str(i), "wordEn": f"word{i}", "pos": "n", "cefrLevel": "A1"} for i in range(1, 4)]
        with open(os.path.join(mock_golden_dir, "golden_v2.json"), "w") as f:
            json.dump(golden_data, f)
            
        exp_id = "EXP-TEST-IMPORT"
        exp_dir = os.path.join(mock_exp_dir, exp_id)
        os.makedirs(exp_dir)
        
        manifest_path = os.path.join(exp_dir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump({
                "progress": {"total": 3},
                "golden_set_id": "golden_v2",
                "golden_set_hash": "dummy",
                "prompt_id": "dummy",
                "prompt_version": "1.0",
                "schema_version": "dummy"
            }, f)
            
        out_dir = os.path.join(exp_dir, "output")
        os.makedirs(out_dir)
        
        out_file = os.path.join(out_dir, "batch_output.jsonl")
        
        # Test A: Successful Output Mapping (All Good)
        with open(out_file, "w") as f:
            f.write(json.dumps({"key": f"{exp_id}-CAND-1", "response": {}}) + "\n")
            f.write(json.dumps({"key": f"{exp_id}-CAND-2", "response": {}}) + "\n")
            f.write(json.dumps({"key": f"{exp_id}-CAND-3", "error": {"code": 500}}) + "\n")
            
        # Should not raise exception
        import_batch_output(exp_id)
        
        # Verify manifest update
        man = load_json(manifest_path)
        self.assertEqual(man["progress"]["completed"], 2)
        self.assertEqual(man["progress"]["failed"], 1)
        
        raw_dir = os.path.join(exp_dir, "raw")
        self.assertTrue(os.path.exists(os.path.join(raw_dir, f"{exp_id}-CAND-3.json")))
        
        # Test B: Missing candidate
        with open(out_file, "w") as f:
            f.write(json.dumps({"key": f"{exp_id}-CAND-1", "response": {}}) + "\n")
            f.write(json.dumps({"key": f"{exp_id}-CAND-2", "response": {}}) + "\n")
            
        with self.assertRaisesRegex(RuntimeError, "CRITICAL MAPPING ERROR"):
            import_batch_output(exp_id)
            
        # Test C: Duplicate candidate
        with open(out_file, "w") as f:
            f.write(json.dumps({"key": f"{exp_id}-CAND-1", "response": {}}) + "\n")
            f.write(json.dumps({"key": f"{exp_id}-CAND-2", "response": {}}) + "\n")
            f.write(json.dumps({"key": f"{exp_id}-CAND-3", "response": {}}) + "\n")
            f.write(json.dumps({"key": f"{exp_id}-CAND-3", "response": {}}) + "\n") # Duplicate
            
        with self.assertRaisesRegex(RuntimeError, "CRITICAL MAPPING ERROR"):
            import_batch_output(exp_id)
            
        # Test D: Unknown candidate
        with open(out_file, "w") as f:
            f.write(json.dumps({"key": f"{exp_id}-CAND-1", "response": {}}) + "\n")
            f.write(json.dumps({"key": f"{exp_id}-CAND-2", "response": {}}) + "\n")
            f.write(json.dumps({"key": f"{exp_id}-CAND-UNKNOWN", "response": {}}) + "\n")
            
        with self.assertRaisesRegex(RuntimeError, "CRITICAL MAPPING ERROR"):
            import_batch_output(exp_id)
            
        shutil.rmtree(mock_exp_dir)
        shutil.rmtree(mock_golden_dir)

if __name__ == "__main__":
    unittest.main()
