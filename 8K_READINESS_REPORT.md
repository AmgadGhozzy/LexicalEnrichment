# 8K READINESS REPORT — LexicalEnrichment

## الخلاصة: **NOT READY (YELLOW / Pilot)**

> البنية الهندسية للـbatch سليمة، لكن model data غير محسوم وجودة content غير مثبتة. التوسع لـ8k الآن سيضاعف البيانات التي لا تثقأن بها.

---

## هل architecture الحالية مناسبة للتوسع 160 → 1000 → 8000؟

| الجانب | الحالة | ملاحظة التوسع |
| --- | --- | --- |
| Batch submission (GCS+JSONL+key) | ✔ ناضج | يعمل؛ لكن `total:160` **hardcoded** في batch_runner.py:133 |
| Golden-set gate | ⚠️ | `entry_count == 160` hardcoded في batch_input_builder.py:30 → يُعاد توليد manifest عند 8k |
| Importer map 1:1 | ✔ | صارم؛ لا مشكلة في العد |
| Filesystem (raw one-file-per-word) | ⚠️ | 8000 ملف؛ يعمل لكن بطيء بلا sharding |
| In-memory readlines الكامل | ⚠️ | `importer:33` و`inspector:53` يقرآن كامل الإخراج → عند 8k كبير لكن محتمل |
| retry/resume | ✖ | لا idempotent resume |
| billing/throttle model | ✖ | لا نموذج تكلفة |
| بيانات Schema | ✖ **خطير** | الـbatch ينتج `enrichment.v1` (4 حقول) لا `lexical_core` (senses…) ← لن يملأ قاعدة الإنتاج |

---

## Quality Gates قبل 8k

```text
Gate 1 — Data integrity          : WordsMaster hash ثابت، golden_v2 hash، encoding سليم (تم التحقق: نظيف UTF-8)
Gate 2 — Prompt evaluation       : ✔ v1.1 (shape) — لكن يلزم جودة أعمق
Gate 3 — Schema validation       : artifact_validator 1.0.0 pass
Gate 4 — Exact lemma compliance  : ✔ 98.13% (EXP-012) — 3 متبقية morphology
Gate 5 — Semantic quality        : ✖ NOT installed — الـvalidator لا يقيّم MNE/ARA/تعريف
Gate 6 — Human review            : ✖ لا يوجد نظري على batch v1.1 (التقريب يخص System A)
Gate 7 — Batch integrity         : ✔ 160/160 (EXP-014)
Gate 8 — Production import       : ✖ data/production فارغ
```

**Gate 5 و 6 هما العائقان.** حتى تعبرهما لا تطلق 8k.

---

## سلسلة الخطوات الآمنة الأقصر من الآن إلى 8k

```text
CURRENT STATE
   (System B batch v1.1 يعمل؛ System A نائم؛ schema مزدوج؛ جودة MNE تراجعت)
      ↓
NEXT GATE        : إثبات جودة content على نطاق 30 من ناتج EXP-014 (LLM judge + human 30)
      ↓
NEXT EXPERIMENT  : EXP-015: مقارنة lexical_core (V2) vs enrichment+v1.1 على نفس الـ30/160
                   - قياس MNE, ARA, DEF, PRN, sense coverage + ثبات schema
      ↓
FREEZE DECISION  : اختيار مخطط واحد (الأفضل) + مصدر CEFR/freq موثوق + إصلاح encoding
                   + أنشئ human workflow للمنيمونيك/العربية
      ↓
BATCH SCALE-UP   : أزل الـhardcoded 160، أضف chunking + retry + billing model
      ↓
HUMAN QA         : عيّنة إلزامية (30 من كل مستوى/stratum) قبل كل إطلاق كبير
      ↓
PRODUCTION       : املأ data/production + توحيد single source of truth
```

---

## Evidence لكل transition

| Transition | Evidence |
| --- | --- |
| Current state = Pilot | EXP-014 ناتج، System A نائم، schema مزدوج |
| Next gate = جودة على 30 | human_ground_truth_30 (اثبت تراجع MNE) → دليل أن بنية المعمارية لا تكفي |
| Next experiment = schema compare | dual-schema موجود بالفعل → نتائجهما قابلة للمقارنة |
| Frozen v1.1 | EXP-010 vs EXP-012 + DECISIONS ADR-001 |
| Batch scale-up شرط | batch_runner.py:133 hardcoded, input_builder:30, no resume |
| Human QA | rubric MNE/ARA جاهز (scoring_rubric) لكن بلا تنفيذ على batch v1.1 |

---

## BigQuery vs Cloud Storage vs Database (توصية)

| السؤال | الجواب |
| --- | --- |
| **Source of truth** | SQLite `db/schema.sql` (words + source_records + field_versions) |
| **Artifact store** | GCS (`gs://lexical-enrichment/experiments/...`) + JSONL |
| **Analytics** | BigQuery **فقط عندما تثبت need** (تحليلات واسعة على 8k+) — لا مقدمًا |
| **Production serving** | `data/production/` SQLite (ومسار إلى DB حقيقي لاحقًا) |

> لا تقدم BigQuery لمجرد الاسم. الـSQLite كافٍ كـsource of truth حتى تنمو analytics فعلًا.

---

## Single Source of Truth (منع "نفس المعلومة في 4 ملفات")

| المعلومة | Canonical Source الوحيد |
| --- | --- |
| lexical identity (lemma/pos/id) | `words` + `source_records` (staging.jsb) |
| frequency/rank | مصدر موثوق مختار (wordfreq/SUBTLex) — ليس الملفات المتناثرة |
| CEFR | جدول CEFR موثوق + levels/units |
| root/family/tree | جدول `word_families` + `sense_relations` (بعد توليد موثوق) |
| curriculum | `levels`/`units` + syllabus منفصل |
| generated enrichment | `word_senses` + `field_versions` (جودة مراجعة بشريًا) |
| human approval | `qa_results` + `sense_status=approved` |

> قاعدة: كل قيمة توجد في مكان واحد; البقية references/derived. ولمنع انجراف حدّث الـ hashes في manifest.
