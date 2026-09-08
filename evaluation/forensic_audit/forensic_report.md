# Forensic Audit — WordsMaster.db vs LexicalStaging.db (READ-ONLY)

**Method:** `mode=ro` SQLite connections, `SELECT`/`PRAGMA` only. Zero writes to either database.
Machine-readable companion: `forensic_report.json` (same directory).

## 0. Snapshot (what exactly was analyzed)

| File | Bytes | mtime (UTC) | SHA-256 |
|---|---|---|---|
| `WordsMaster.db` | 10,399,744 | 2026-03-02 | `cfabafa8…86984f9` (full hash in JSON) |
| `data/staging/LexicalStaging.db` | 21,954,560 | 2026-09-03 | `8f1a382d…add060` (full hash in JSON) |

> Note: you said 8,000 words — the on-disk `WordsMaster.db` holds **7,300** rows.

## 1. Inventory

**WordsMaster:** `levels`(6) → `units`(136) → `wordsMaster`(7,300, flat 39-column enrichment). No indexes, no views, no triggers.
Unit counts per level: A1 18 / A2 19 / B1 20 / B2 38 / C1 37 / C2 4 (C2 = 182 words only).

**LexicalStaging:** normalized rebuild shell — `words`(8,027) + `source_records`(8,027) + `categories`(12) populated;
**all enrichment tables are at 0 rows** (`word_senses`, `examples`, `pronunciations`, `sense_translations`,
`sense_relations`, `collocations`, `word_families`, `field_versions`, `qa_results`, …). 18 indexes, no views/triggers.
The rebuild has **not started** — staging is a migration shell with source snapshot + one recomputed column.

## 2. 🔴 Provenance flag (HIGH)

The on-disk `WordsMaster.db` (7,300 rows, March) **is not** the database staging was imported from:
`source_records` claims `source_db=WordsMaster.db` with `source_row_id` up to **8,027**, and the 727 extra rows
carry a **different serialization vintage** (array-encoded `definitionEn`/`examples`, truncated phonetics
`"pɹə-"`, null `definitionAr`/`usageNote`/`primarySense`/`mnemonicAr`). A newer/larger WordsMaster existed in
September and is not on disk. **Resolve this snapshot mismatch before any migration.**

The 727 extras are **quarantine-grade**: partial records + dubious function-word POS
(`the`/noun, `and`/noun, `to`/verb). Never feed them to the 1,000-pilot.

## 3. Numeric forensics — your fear was justified

- **`rank` == row `id` for 7,300/7,300.** It is not a frequency rank; it is a row number wearing a lab coat.
  Same for staging `frequency_rank` (8,027/8,027). Recompute real ranks from frequency if needed; do not treat as signal.
- **`frequency` (1–6) is coherent**: anchors `the`=1, `time`=2, `run/telephone`=3–4, `gastric/prestigious`=5.
  Scale: 1 = most frequent … 6 = rarest. KEEP.
- **`difficultyScore` is a banded heuristic recycling CEFR+frequency, not a measurement.**
  Bands are near-deterministic per level (diff 2 → A1 only … diff 10 → C2 only) with scatter, and staging
  **silently recomputed 79% of values** (agreement with master: 1,514/7,300 = 21%, scattered non-monotonically).
  Verdict: **recompute transparently or drop** — never present as measured difficulty.

## 4. Field verdicts (Keep / Regenerate / Deterministic)

| Field | Legacy quality | Legacy problem | Keep | Regen | Determ |
|---|---|---|---|---|---|
| lemma/POS/register/CEFR/category/primarySense/fromOxford | authoritative curriculum data; 789 dup lemmas = all clean POS variants, 0 exact dup pairs | — | ✓ | | |
| frequency 1–6 | coherent band, anchor-verified | document the scale | ✓ | | |
| rank / frequency_rank | row numbers, not measurements | leakage rank→ID | | | ✓ derive |
| difficultyScore | banded CEFR+frequency heuristic | fake precision; staging recomputed 79% undocumented | | | ✓ recompute openly |
| definitionEn | clean (p50 59ch, max 130, 0 nulls) | — | ✓* | | |
| definitionAr | healthy body, **Egyptian dialect** throughout | 2,893ch grounding-leak outlier; dialect is a product decision | | ✓/normalize? | strip URLs |
| arabicAr + 9 translations | **good** — classic false friends verified correct (`pain`→douleur, `sale`→venta, `chair`-verb→présider) | ~1,543 eq-wordEn forms, mostly true cognates → spot-check, don't assume | ✓* | | |
| IPA Us/Ar + translit | complete (0 nulls) | **UK missing 48%** (3,480, unpatterned source gap) | ✓ | | fill UK via dictionary |
| syllabify | `•`-separated, fine | 34% nulls (nouns/verbs) | | | ✓ rule fill |
| examples (6 CEFR cells × 7,300) | full coverage, sane lengths | **fails our exact-lemma rule at 14.8%** (mostly inflections); 34 placeholder cells; `(Standard equivalent)` annotation suffixes; 176 cross-word shared sentences | | ✓ | |
| synonyms/antonyms/collocations/related/wordFamily | valid JSON everywhere; `[]` rates legitimate (antonyms 30%, synonyms 80 function words, family nulls = non-inflecting POS) | run v2.2.2 substitution audit on compounds | ✓* | | |
| mnemonicAr (94% populated) | hook style **matches our target philosophy** (`Tour`→`To`, `Hand`→`And`) | **1,630 etymology-claim candidates** need sampled adjudication under v2.2.3; 439 nulls mostly justified function words | ✓* | | |
| usageNote | clean pedagogical notes | 3,298ch grounding-leak outlier | ✓* | | strip |
| staging 727 extras | partial low-quality vintage | truncated phonetics, null core fields, dubious POS | QUARANTINE | | |

✓* = keep with the stated audit/spot-check.

## 5. Examples audit (43,800 cells)

- Exact-token lemma present: **37,310 (85.2%)**; absent: **6,490 (14.8%)** — absent bucket dominated by
  inflected forms (`was/has/them/getting/peoples/others`), i.e. exactly what our exact-lemma rule forbids.
  **Regeneration (not keep) is the correct call for examples.**
- `<3 words`: 69 (legit interjections). Missing terminal punctuation: 42 (incl. annotation suffixes).
- Duplicates within word: 0. Shared sentences across words: 176 (function-word overlap, benign).
- Placeholders (`Not used in X contexts`): 34 cells (0.08%) — negligible but strip deterministically.

## 6. Contamination (isolated, strippable)

- Google-grounding citation leakage (`grounding-api-redirect` URLs + `[[1]` markers) in **2 rows**
  (`homemade` definitionAr, `migrate` usageNote). Deterministic strip; add a CI guard so the new pipeline never emits URLs into content fields.

## 7. Answer to your quality-ceiling question

**v2.2.3 is not the ceiling — it is the best *proven* setup.** The audit says the biggest remaining levers are
**not** temperature/thinking games but:

1. **Deterministic preprocessing** — IPA-UK fill, syllabify fill, grounding-strip, transparent difficulty. Zero LLM cost, pure quality floor-raising.
2. **Examples regeneration under the exact-lemma rule** — legacy fails it at 14.8%; this alone justifies the LLM budget.
3. **Keep (don't re-pay for) solved fields** — translations, IPA, definitions-En, relations are legacy-strong. Regenerating them with the LLM buys risk, not quality. The winning architecture is **hybrid: deterministic keep + LLM regenerate for the weak fields**, which is also far cheaper at 1,000-word scale.
4. **Etymology-claim audit** on legacy mnemonics before any bulk keep.

## 8. Recommended 1,000-pilot composition (given findings)

Sample from authoritative **WordsMaster 7,300** (never staging extras): stratified CEFR×POS, skip the 100 done,
pre-fill deterministic fields (IPA-UK/syllabify/artifact-strip), LLM-generate only definitionAr/examples/
mnemonic/senses under locked v2.2.3, human-evaluate per the HR-10x protocol. Await your approval on the source list before any launch.
