"""Pilot batch input builder (build ticket 12, full run).

Builds the Vertex batch JSONL from the FROZEN pilot manifest —
never resamples, never regenerates the manifest. Envelope format
mirrors the repo batch input builder exactly (contents +
generationConfig camelCase + optional thinking/tools), pinned to
the exact v2.2.3 configuration. Master rows are read-only input
(lemma/POS source of truth for prompt fill); CEFR prompt input is
the manifest's evidence label, recorded as such.

Bounds enforced here: frozen-sample intactness (request ids ==
manifest ids, asserted), config fidelity (no mid-run changes
possible — config is an argument, hashed into the build record).
"""

import hashlib
import json
import os

V223 = {
    "prompt_id": "lexical_enrichment_final_m3",
    "prompt_version": "2.2.3",
    "schema_version": "lexical_output.v1.1-candidate",
    "model_id": "gemini-3.8-flash",
    "temperature": 1.0,
    "max_output_tokens": 8192,
    "thinking_level": "low",
    "grounding": False,
}

EXPERIMENT_ID = "PILOT-V1"


def build_envelope(entry, master_row, prompt_template, schema_stripped,
                   config=V223):
    """One {key, request} envelope for a manifest entry.

    master_row: (lemma, pos) read-only master values. Raises on any
    id/lemma/pos mismatch between manifest entry and master row —
    the frozen sample must not drift.
    """
    mid, lemma, pos = master_row
    if mid != entry["id"] or lemma != entry["lemma"] or pos != entry["pos"]:
        raise ValueError("manifest/master drift for id %r" % (entry["id"],))
    prompt_text = prompt_template.format(
        lemma=lemma, pos=pos, cefr=entry["stratum"][0], id=mid)
    gen_config = {
        "temperature": config["temperature"],
        "maxOutputTokens": config["max_output_tokens"],
        "responseMimeType": "application/json",
        "responseSchema": schema_stripped,
        "thinkingConfig": {"thinkingLevel": config["thinking_level"]},
    }
    return {
        "key": "%s-CAND-%s" % (EXPERIMENT_ID, mid),
        "request": {
            "contents": [{"role": "user",
                          "parts": [{"text": prompt_text}]}],
            "generationConfig": gen_config,
        },
    }


def build_input(manifest_entries, master_lookup, prompt_template,
                schema_stripped, out_path, config=V223):
    """Write the full batch JSONL. Returns a build record dict.

    Asserts the request id set equals the manifest id set exactly
    (frozen-sample intactness). Returns keys: path, sha256, count,
    config_fingerprint (hash of the effective config).
    """
    lines = []
    for entry in manifest_entries:
        mid = entry["id"]
        if mid not in master_lookup:
            raise ValueError("manifest id %r missing from master" % (mid,))
        lines.append(json.dumps(
            build_envelope(entry, master_lookup[mid], prompt_template,
                           schema_stripped, config),
            ensure_ascii=False))
    manifest_ids = sorted(e["id"] for e in manifest_entries)
    request_ids = sorted(
        int(json.loads(line)["key"].rsplit("-", 1)[1]) for line in lines)
    if request_ids != manifest_ids:
        raise ValueError("request ids diverge from frozen manifest")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    digest = hashlib.sha256(
        open(out_path, "rb").read()).hexdigest()
    return {
        "path": out_path,
        "sha256": digest,
        "count": len(lines),
        "manifest_ids": manifest_ids,
        "config": dict(config),
        "config_fingerprint": hashlib.sha256(
            json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest(),
    }
