"""
Shared utilities for the LexicalEnrichment evaluation pipeline.

Used by both evaluation_runner.py and artifact_validator.py.
No Vertex AI / Gemini SDK dependencies — strictly deterministic.
"""

import os
import json
import hashlib
import re
import importlib.metadata
from datetime import datetime, timezone

# ---------------------------------------------------------
# Project Paths
# ---------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT_DIR, "evaluation")
GOLDEN_SET_DIR = os.path.join(ROOT_DIR, "golden_set")
EXPERIMENTS_DIR = os.path.join(EVAL_DIR, "experiments")
CONFIGS_DIR = os.path.join(EVAL_DIR, "configs")
PROMPTS_DIR = os.path.join(EVAL_DIR, "prompts")
SCHEMAS_DIR = os.path.join(PROMPTS_DIR, "schemas")

# ---------------------------------------------------------
# Time
# ---------------------------------------------------------
def utc_now():
    """ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------
# Hashing
# ---------------------------------------------------------
def canonical_hash(obj):
    """Generate a consistent SHA-256 hash for JSON-serializable objects.

    Strings are hashed as raw UTF-8 bytes.
    Everything else is serialised with sorted keys and compact separators
    before hashing, guaranteeing reproducibility.
    """
    if isinstance(obj, str):
        encoded = obj.encode('utf-8')
    else:
        encoded = json.dumps(
            obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()

def get_file_hash(filepath):
    """SHA-256 of raw file bytes.  Returns None if file is missing."""
    if not os.path.exists(filepath):
        return None
    return hash_file_bytes(filepath)


def hash_file_bytes(filepath):
    """SHA-256 of raw file bytes.  Raises FileNotFoundError if missing."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def sha256_string(s):
    """SHA-256 of a raw UTF-8 string.  Equivalent to canonical_hash on a str."""
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

# ---------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------
def load_json(filepath):
    """Read a JSON file with UTF-8 encoding."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(filepath, data):
    """Write a JSON file with UTF-8 encoding, 2-space indent, no ASCII escaping."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_file(filepath):
    """Read a text file with UTF-8 encoding."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(filepath, text):
    """Write a text file with UTF-8 encoding."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

# ---------------------------------------------------------
# Experiment helpers
# ---------------------------------------------------------
def generate_experiment_id(prefix="EXP"):
    """Next sequential experiment id in the form PREFIX-YYYY-MM-DD-NNN."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pattern = re.compile(rf"^{re.escape(prefix)}-{re.escape(date_str)}-(\d{{3}})$")
    numbers = []
    if os.path.exists(EXPERIMENTS_DIR):
        for name in os.listdir(EXPERIMENTS_DIR):
            match = pattern.match(name)
            if match:
                numbers.append(int(match.group(1)))
    seq = max(numbers, default=0) + 1
    return f"{prefix}-{date_str}-{seq:03d}"

def get_sdk_version():
    """Installed google-genai SDK version, or 'unknown' if not installed."""
    try:
        return importlib.metadata.version("google-genai")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
