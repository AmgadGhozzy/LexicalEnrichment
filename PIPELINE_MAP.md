# PIPELINE MAP — LexicalEnrichment
*(سمّيت النظامين كما هما فعليًا في الكود)*

لدينا **نظامان منفصلان فعليًا**، وليس pipeline واحدة. هذا هو السبب الجوهري في "وجود أكثر من pipeline".

---

## SYSTEM A — V2 Production Engine (`pipeline/` + `config/` + `db/`)

الهدف: توليد قاعدة معجمية غنية (senses, relations, translations, families) حسب مخطط `db/schema.sql` (16 جدول).

| الملف | الدور | الإدخال | الإخراج | مدى النشاط |
| --- | --- | --- | --- | --- |
| `pipeline/phase0_preflight.py` | فحص أولي (hash/ذمة) | `WordsMaster.db` (path مكمّد) | تقرير | Legacy/standalone |
| `pipeline/phase0_audit_import.py` | ETL استيراد | `WordsMaster.db` | `data/staging/LexicalStaging.db` (words, source_records) | **تم (8027 كلمة)** |
| `pipeline/llm_provider.py` | موصل Vertex AI (System A فقط) | — | — | نشط لـA |
| `pipeline/phase1_lexical_core.py` | توليد senses | words من staging | word_senses, pronunciations, field_versions | **تم (10 كلمات smoke، 27 sense)** |
| `pipeline/phase_eval_runner.py` | تقييم منعزل لقسم A | legacy_baseline_200 | evaluation_runs, word_evaluations | **تم (205 تقييم)** |
| `pipeline/phase_eval_machine.py` | تسجيل آلي للناتج | word_evaluations | scores/decisions | تم |

**تشخيص:** System A هو "الخط الإنتاجي المقصود" لكنه **نائم جزئيًا**:
- `data/production/` **فارغ** — لا يوجد أي writeback إنتاجي.
- مراحل 2–4 (examples, collocations, relations, translations, word_families, learner_notes, ielts_metadata) **لم تُكتب ولو سطر** — كل الجداول فارغة في staging.
- `phase1_lexical_core.py` **مربوط hardcoded بقائمة 10 lemmas**، لا يقبل 8k.
- prompt/schema على القرص (`lexical_core.md`/`.json`) **أحدث من** التي أنتجت الـrun (hash مختلف) → من تغيّر بعد التشغيل.

### Schema المستخدم في A: `config/schemas/lexical_core.json` (words[].senses[] — متعدد المعاني)
### Prompt المستخدم في A: `prompts/system|tasks/lexical_core.md`

---

## SYSTEM B — Evaluation / Batch System (`evaluation/` + `evaluation_runner.py`)

الهدف: قياس compliance وتجريب التوليد وتشغيل Batch Prediction.

| الملف | الدور |
| --- | --- |
| `evaluation_runner.py` (root) | أوّل Online Runner → أنتج EXP-001..012 |
| `evaluation/batch_runner.py` | إرسال Vertex Batch Job → EXP-013/014 |
| `evaluation/batch_input_builder.py` | بناء JSONL (key+request) |
| `evaluation/batch_importer.py` | map الإخراج إلى golden set (1:1 صارم) |
| `evaluation/batch_output_inspector.py` | تنزيل output من GCS |
| `evaluation/batch_comparison.py` | مقارنة online vs batch |
| `evaluation/artifact_validator.py` | validations حتمية (schema, target, mnemonic, circular…) |
| `evaluation/utils.py` | أدوات مشتركة (hash, paths) |

**انتاج System B النشط:** `evaluation/experiments/EXP-*`.

### Schema المستخدم في B: `evaluation/prompts/schemas/enrichment.v1.json` (definition_en/explanation_ar/examples[]/mnemonic_ar فقط)
### Prompt المستخدم في B: `evaluation/prompts/lexical_enrichment_v1.1.txt`

---

## الفجوة الجوهرية

| | System A | System B |
| --- | --- | --- |
| Schema | lexical_core (غني، senses) | enrichment.v1 (خفيف، 4 حقول) |
| Prompt | lexical_core.md | lexical_enrichment_v1.1.txt |
| LLM wrapper | llm_provider.py (VertexAIProvider) | google.genai مباشرة |
| الإخراج | staging DB | experiments/ JSON per-word |
| الحالة | نائم جزئيًا (10 كلمات) | **نشط (160 batch pilot)** |

**System B لا يقرأ ولا يكتب في System A ولا في `config/schemas/lexical_core.json`.** الاثنان **غير متصلين**. المشاركة الوحيدة: `evaluation/utils.py`.

> **الخلاصة:** البيانات التي أنتجها Batch Pilot (EXP-014) **ليست** في الشكل الذي تحتاجه قاعدة الإنتاج. الـ160 ناتجًا من الـbatch لا تمتلك senses/collocations/translations/relations التي صُمم لها `db/schema.sql`.

---

## تحديث التوصية — بنية مستهدفة واحدة نظيفة

بدل الفصل الحالي، نوحّد على:

```text
01_data_sources/      (WordsMaster.db + IeltsWord.db كمراجع immutable)
02_normalization/     (apply الدروس من legacy إلى V2)
03_lexical_metadata/  (lemma,pos,cefr,rank,freq,root,family — deterministic)
04_curriculum/        (levels/units — من مستوى منفصل)
05_prompts/           (نموذج واحد: lexical_core الموسّع)
06_generation/        (Batch — Vertex)
07_experiments/       (EXP-*)
08_batch/             (runner/input/importer/inspector)
09_validation/        (artifact_validator + الجودة)
10_human_review/      (workflow mnemonic/arabic)
11_production/        (db خدمة)
12_archive/           (كل ما هو متروك)
```

> لا تعيد تنظيم الملفات الآن. هذا mapping للاتجاه فقط.
