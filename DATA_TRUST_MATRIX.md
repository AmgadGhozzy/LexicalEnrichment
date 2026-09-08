# DATA TRUST MATRIX — LexicalEnrichment
*تصنيف كل حقل/مصدر من حيث الموثوقية وهل يُعاد توليده.*

> **قاعدة مفتاحية:** أي حقل **deterministic + source-backed + reproducible** → لا يُعاد توليده بالـLLM. أي حقل **تعليمي/إبداعي** → قد يستفيد من LLM + مراجعة بشرية.

---

## 1. Golden Set 160 — الأعمدة الفعلية (من golden_v2.json)

| الحقل | النوع | المصدر | Trust | Immutable? | Regeneration? |
| --- | --- | --- | --- | --- | --- |
| id | int | WordsMaster | High | ✔ | لا |
| wordEn (lemma) | string | WordsMaster | High | ✔ | لا |
| pos | enum | WordsMaster | High | ✔ | لا |
| cefrLevel | enum A1-C2 | WordsMaster | Med (مصدر مجهول) | ✔ | لا (لا للـLLM) |
| fromOxford | int 0/1 | WordsMaster | Med | ✔ | لا |
| rank | int (1..7300) | WordsMaster | Med | ✔ | لا |
| frequency | int 1-6 (band) | WordsMaster | Med | ✔ | لا |
| difficultyScore | int 2-10 | WordsMaster | Med | ✔ | لا |
| syllabify | string/null | Legacy | Low | ✔ | لا |
| phoneticUs/Uk | IPA | Legacy source | **High** (نظيف عند قراءة UTF-8) — انظر ملاحظة encoding | ✖ | تحقق عيّنة فقط |
| phoneticAr | عرب | Legacy source | **High** (نظيف) | ✖ | تحقق عيّنة فقط |
| translit | عرب-إنجليزي | Legacy source | Med | ✖ | نعم (بعد الاتفاق على Policy) |
| definitionEn / Ar | نص | Legacy | Med | ✖ | عن LLM (خاضع) |
| usageNote | نص | Legacy | Med | ✖ | عن LLM |
| category | enum | Legacy/LLM | Med | ✖ | عن LLM |
| primarySense | enum | LLM | Med | ✖ | عن LLM |
| semanticTags | array | LLM | Low-Med | ✖ | عن LLM |
| register | enum | LLM | Med | ✖ | عن LLM |
| mnemonicAr | نص null | Legacy + V2 | **Low** (V2 تراجع بشريًا) | ✖ | **نعم + human review** |
| examples (A1-C2 6) | JSON | Legacy | Med | ✖ | عن LLM (Phase 2) |
| collocations | array | Legacy | Med | ✖ | عن LLM (Phase 3) |
| synonyms/antonyms | array | Legacy | Med | ✖ | عن LLM (Phase 3) |
| relatedWords | JSON en/ar | Legacy | Low | ✖ | عن LLM |
| wordFamily | JSON noun/verb/adj/adv | Legacy | Med | ✖ | تحقق (morphology) |
| arabicAr..turkishTr (10) | نص | Legacy | **Questionable** (encoded مشوّه?) | ✖ | إعادة توليد (Phase 4) |
| unitId | string (A1_18) | WordsMaster units | High | ✔ | لا |
| stratum | كمّ stratify | Builder | High | ✔ | لا |
| in_ielts | bool | IELTS overlap | High | ✔ | لا |

### ملاحظة encoding (تصحيح مهم بعد فحص دقيق)
في العرض الأول (عبر terminal بترميز cp1252) ظهرت قيم مثل `"'tra?z?rz"` و`"????????"` و`"?? (W�iyang)"`. الفحص الدقيق عبر القراءة الصحيحة UTF-8 أثبت أن **المصدر والـgolden_v2 نظيفان**:
- WordsMaster id=6067 → Arabic `بنطلون`، Chinese `裤子 (Kùzi)`، IPA `ˈtraʊzərz` — كلها صحيحة.
- golden_v2 id=6067 → نفس القيم النظيفة.
- عدّ المصدر: 0 replacement chars في arabicAr/chineseZh/phoneticUs/phoneticAr/japaneseJa؛ فقط 2 قيم `?` في definitionAr.

**الخلاصة:** لا يوجد تلف encoding فعلي. المظهر المشوّه كان صك قراءة خاطئ (cp1252). **لا حاجة لإعادة توليد الـphonetics/الترجمات لأجل الترميز.** تبقى طبعًا مسألة الجودة والـprovenance المنفصلة.

---

## 2. تقسيم البيانات القديمة (WordsMaster.db — 7,300 كلمة)

| فئة | الأمثلة | القرار |
| --- | --- | --- |
| **Immutable Trusted** | id, lemma, pos, cefr, unitId, fromOxford | احتفظ دون LLM |
| **Derived (deterministic)** | rank, frequency band, difficultyScore | احتفظ كمرجع (compute قابلة لإعادة الحساب بمصدر أفضل) |
| **Questionable (تحتاج verify)** | frequency/rank **original**, difficultyScore, CEFR source | source قديم مجهول → **VERIFY** أو صهر مع مصدر موثوق |
| **LLM-geneable** | definitionEn/Ar, usageNote, examples, collocations, relations, family | توليد + تقييم |
| **Obsolete/مشوّه** | phonetic* والترجمات ذات بـ `?`/`�` | **REGENERATE** (Encoding غير صالح) |

---

## 3. قرار كل حقل (التوصية النهائية)

| الحقل | SOUCE OF TRUTH | Regenerate? | Human review? |
| --- | --- | --- | --- |
| lemma/pos/id | WordsMaster (immutable) | لا | لا |
| cefr | ✖ (مصدر مجهول) — صهّر مع CEFR dictionary موثوق | لا (فقط verify) | نعم (عيّنة) |
| rank/frequency | ✖ — استبدل بـ wordfreq/SUBTLex موثوق | **نعم (إعادة حساب deterministic)** | لا |
| difficultyScore | مشتق | إعادة حساب | لا |
| root/family/tree | غير موجود في القديم | **جديد عن LLM + morphology tool** | نعم (عيّنة) |
| phonetic_us/uk | Legacy source نظيف | تحقق عيّنة لا إعادة | عيّنة |
| phonetic_ar | Legacy source نظيف | تحقق عيّنة | عيّنة |
| definition_en/ar | Legacy (Pedagogical gold) — لاحظ الفشل | عن LLM لكن legacy قد يكون أفضل | **نعم** |
| mnemonic_ar | Legacy كان `MNE=5`، V2 `MNE=0` | **نعم لكن بشرط تجاوز legacy** | **نعم إلزامي** |
| examples/collocations/synonyms/antonyms/family | جديد | **نعم (Phase 2-4)** | عيّنة |
| translations ×10 | Legacy مصدر نظيف | **لا إعادة لأجل encoding** — تحقق جودة فقط | عيّنة |

---

## 4. IELTS (بيانات الـapp)

| سؤال | جواب |
| --- | --- |
| موجودة؟ | ✔ (IeltsWord.db 1,022 كلمة + ielts1-19 txt) |
| المصدر؟ | Android app dump (مستخرج) |
| provenance؟ | ✖ ضعيف (BOM `\ufeff`، بعض المشاكل في القيم) |
| قانوني؟ | area رمادية (dump موزَّع) — استخدم كـauxiliary signal فقط |
| قيمة؟ | topics, definitions, examples, IPA audio/images — مفيدة pedagogically |
| الميزة؟ | `ar_Arabic` + ~50 لغة، topics، audio/images |
| القرار | **KEEP AS AUXILIARY SIGNAL** — metadata/multimedia، لا مصدر رئيسي لـranking، لا CEFR منه |

> لا تستخدم IELTS كمرجع إلزامي لـranking/CEFR. استخدمه لإثراء (topics, examples, audio, cross-language) بعد مراجعة شرعية.

---

## 5. ترتيب/إضافة كلمة جديدة (canonical rule)

```text
word
  → normalize (lemma, lowercase, strip)
  → deduplicate (word+pos)
  → frequency (wordfreq / corpus موثوق)   ← وليس القديم المبهم
  → rank        (ordinal من frequency)
  → difficulty  (derive من frequency + polysemy + POS)
  → CEFR        (من مصدر موثوق أو inferred) 
  → unit assign (من مستوى منفصل، ليس من rank مباشرة)
  → production id
```

- **rank**: ديناميكي ومشتق من frequency الساعية، وليس ثابتًا. إذا تغيّرت بيانات frequency مستقبلًا، يُعاد الحساب.
- **ملاحظة مهمة**: لا تجعل `rank` مرادفًا لـ `CEFR` أو `unit`. هي مفاهيم منفصلة (انظر القسم التالي).

---

## 6. Levels + Units (التمييز المطلوب)

| المفهوم | التعريف | الأساس |
| --- | --- | --- |
| **Lexical Rank** | ترتيب حسب التكرار | frequency |
| **CEFR Level** | مستوى إتقان لغوي (A1-C2) | معايير معجمية |
| **Course/App Level** | مستوى تقدم المتعلم (Unit بعينه) | منهج تعليمي |
| **Unit** | تجميع (مثل أسبوع/10 كلمات) | curriculum/pedagogy + تسلسل |

> في القديم كان `unitId` (مثل `A1_18`) مبنيًا على CEFR فقط. البنية المستهدفة يجب أن تفصل unit كمنتج تعليمي قابل لإعادة الترتيب دون كسر rank/CEFR.

---

## 7. Memory Hook / Mnemonic — النتيجة الأدق

- **مولّد؟** نعم، في كلا النظامين (قابل null حسب schema).
- **اختياري؟** نعم (nullable).
- **كيف يتعامل validator؟** `artifact_validator` يرفض generic-null (`لا يوجد`) فقط، ولا يفحص جودة.
- **هل Golden يحتويه؟** نعم (لكن أغلبها Legacy ذو `MNE=5`).
- **هل v1.1 يولّده؟** نعم (instruction + schema).
- **هل قابلة للتقييم آليًا؟** **لا، حتى الآن.** الـartifact_validator لا يقيّم "retrieval value". الـLLM judge يمكن أن يقترب لكن الإنسان هو المرجع.
- **المشكلة المؤكّدة:** **human_ground_truth_30.csv** أثبت أن V2 يولّد `MNE=0` (مجرد paraphrase/تعريف) بينما Legacy `MNE=5` — **تراجع**. الجودة غير قابل للtrust حاليًا.

**workflow مقترح (إلزامي قبل 8k):**
```text
LLM generates mnemonic
  → automated checks (structure: quotes, no parens, non-generic)
  → LLM judge (weak signal)
  → HUMAN review (حاسم — عيّنة 30 للتحقق)
  → approved / rejected
```
- `mnemonic_ar` **يجب أن يكون human-reviewed ومباشرة من مصدر متى أمكن** — لا توليد أعمى عند 8k.
