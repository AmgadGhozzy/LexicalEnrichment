"""Batch transport for the blind AI judge (Phase: adjudication).

Single-phase batch: every eval_id is pre-audited (artifact/schema/
hash/identity) inside the *_348 package; the judge ONLY adjudicates
A/B arms of already-validated cards. Model input is the frozen
ai-rubric-v3 rubric + the canonical blind view (ai_judge
.build_judge_prompt) — no candidate/legacy labels, no provenance,
no identities beyond the card itself.

Transport pins (test-enforced): temperature 0.0, maxOutputTokens
4000, responseMimeType application/json, thinkingLevel low,
location global. import_ballots() is pure and deterministic:
  - "error" lines   -> rejects[key] = "batch_api_error"
  - unparsable JSON -> malformed += 1 (never guessed)
  - contract breach -> rejects[key] = JudgeError reason
  - missing output  -> rejects[key] = "missing_output"
Taken ballots are stored VERBATIM; nothing is repaired or defaulted.
"""

import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.ai_judge import build_judge_prompt, parse_ballot

MODEL_ID = "gemini-3.8-flash"
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 4000
THINKING_LEVEL = "low"
MIME_TYPE = "application/json"


def build_requests(items):
    """items -> one request dict per card, fixed transport shape."""
    requests = []
    for item in items:
        prompt = build_judge_prompt(item)
        requests.append({
            "key": item["eval_id"],
            "request": {
                "model": MODEL_ID,
                "generationConfig": {
                    "temperature": TEMPERATURE,
                    "maxOutputTokens": MAX_OUTPUT_TOKENS,
                    "responseMimeType": MIME_TYPE,
                    "thinkingConfig": {"thinkingLevel": THINKING_LEVEL},
                },
                "contents": [{"parts": [{"text": prompt}]}],
            },
        })
    return requests


def import_ballots(lines, eval_ids):
    """Parse batch lines into (judgments, rejects, malformed)."""
    judgments = {}
    rejects = {}
    malformed = 0
    seen = set()
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            malformed += 1
            continue
        key = rec.get("key")
        if not isinstance(key, str):
            malformed += 1
            continue
        seen.add(key)
        if "error" in rec:
            rejects[key] = "batch_api_error"
            continue
        try:
            text = rec["response"]["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            rejects[key] = "missing_output"
            continue
        try:
            judgments[key] = parse_ballot(text)
        except Exception as exc:
            rejects[key] = str(exc)
    for eval_id in eval_ids:
        if eval_id not in seen and eval_id not in judgments:
            rejects[eval_id] = "missing_output"
    return judgments, rejects, malformed


def save_ballots(judgments, rejects, malformed, out_path):
    payload = {
        "judgments": judgments,
        "rejects": rejects,
        "malformed": malformed,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return out_path


def load_ballots(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)