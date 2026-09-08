-- ============================================================================
-- Lexical Enrichment Engine v2.0 — Production Schema
-- ============================================================================
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA foreign_keys = ON;

-- ============================================================================
-- 0. RUNS & CATEGORIES (created first — FK dependencies)
-- ============================================================================
CREATE TABLE IF NOT EXISTS enrichment_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_mode        TEXT    NOT NULL CHECK (run_mode IN ('test','evaluation','production')),
    stage           TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    model_version   TEXT,
    prompt_version  TEXT    NOT NULL,
    prompt_hash     TEXT    NOT NULL,
    schema_version  TEXT    NOT NULL,
    schema_hash     TEXT    NOT NULL,
    batch_size      INTEGER NOT NULL,
    words_processed INTEGER DEFAULT 0,
    words_passed    INTEGER DEFAULT 0,
    words_failed    INTEGER DEFAULT 0,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cost_estimate   REAL    DEFAULT 0.0,
    started_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    finished_at     TEXT,
    status          TEXT    DEFAULT 'running'
                    CHECK (status IN ('running','completed','failed','cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_runs_stage  ON enrichment_runs(stage);
CREATE INDEX IF NOT EXISTS idx_runs_status ON enrichment_runs(status);

CREATE TABLE IF NOT EXISTS categories (
    name TEXT PRIMARY KEY
);

INSERT OR IGNORE INTO categories(name) VALUES
    ('General / Common'),
    ('Social Life & Communication'),
    ('Work & Business'),
    ('Actions & Processes'),
    ('Objects & Tools'),
    ('Mind & Thinking'),
    ('Numbers, Time & Math'),
    ('Food & Drink'),
    ('Travel & Movement'),
    ('Nature & Science'),
    ('Feelings & Emotions'),
    ('Health & Senses');

-- ============================================================================
-- 1. CORE WORD IDENTITY
-- ============================================================================
CREATE TABLE IF NOT EXISTS words (
    id               INTEGER PRIMARY KEY,
    lemma            TEXT    NOT NULL,
    normalized_lemma TEXT    NOT NULL,
    pos              TEXT    NOT NULL,
    cefr_level       TEXT    NOT NULL CHECK (cefr_level IN ('A1','A2','B1','B2','C1','C2')),
    frequency        REAL    DEFAULT 0.0,
    frequency_rank   INTEGER DEFAULT 0,
    difficulty_score TEXT,
    oxford_flag      INTEGER DEFAULT 0,
    category         TEXT    REFERENCES categories(name),
    syllabify        TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_words_lemma    ON words(normalized_lemma);
CREATE INDEX IF NOT EXISTS idx_words_pos      ON words(pos);
CREATE INDEX IF NOT EXISTS idx_words_cefr     ON words(cefr_level);
CREATE INDEX IF NOT EXISTS idx_words_category ON words(category);

-- ============================================================================
-- 2. WORD SENSES
-- ============================================================================
CREATE TABLE IF NOT EXISTS word_senses (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id           INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    sense_no          INTEGER NOT NULL DEFAULT 1,
    definition_en     TEXT,
    definition_ar     TEXT,
    short_def_en      TEXT,
    register          TEXT,
    domain            TEXT,
    is_primary        INTEGER NOT NULL DEFAULT 0,
    usage_note        TEXT,
    mnemonic_ar       TEXT,
    primary_sense     TEXT,
    semantic_tags     TEXT,    -- JSON array; validated by Phase 5 deterministic QA
    sense_status      TEXT     DEFAULT 'generated'
                      CHECK (sense_status IN (
                          'generated','qa_passed','qa_failed',
                          'approved','rejected','needs_review'
                      )),
    source_evidence   TEXT,
    enrichment_run_id INTEGER REFERENCES enrichment_runs(id),
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(word_id, sense_no)
);

CREATE INDEX IF NOT EXISTS idx_senses_word   ON word_senses(word_id);
CREATE INDEX IF NOT EXISTS idx_senses_status ON word_senses(sense_status);

-- Invariant: exactly one primary sense per word (partial unique index)
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_primary_per_word
    ON word_senses(word_id) WHERE is_primary = 1;

-- ============================================================================
-- 3. PRONUNCIATIONS  (word-level; phonetic_ar = English phoneme in Arabic script)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pronunciations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id    INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    variant    TEXT    NOT NULL CHECK (variant IN ('us','uk','ar')),
    ipa        TEXT,    -- NO slashes, e.g. əˈtʃiːv
    phonetic_ar TEXT,   -- Half Tashkeel; Arabic script of English pronunciation
    source     TEXT    DEFAULT 'seed',
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(word_id, variant)
);

-- ============================================================================
-- 4. EXAMPLES  (sense-level)
-- ============================================================================
CREATE TABLE IF NOT EXISTS examples (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sense_id          INTEGER NOT NULL REFERENCES word_senses(id) ON DELETE CASCADE,
    cefr_level        TEXT    NOT NULL CHECK (cefr_level IN ('A1','A2','B1','B2','C1','C2')),
    text              TEXT    NOT NULL,
    is_ielts_relevant INTEGER DEFAULT 0,
    ielts_skill       TEXT    CHECK (ielts_skill IN ('writing','speaking','reading','listening')),
    context_domain    TEXT,
    qa_status         TEXT    DEFAULT 'generated',
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_examples_sense ON examples(sense_id);

-- ============================================================================
-- 5. COLLOCATIONS  (sense-level)
-- ============================================================================
CREATE TABLE IF NOT EXISTS collocations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sense_id    INTEGER NOT NULL REFERENCES word_senses(id) ON DELETE CASCADE,
    collocation TEXT    NOT NULL,
    type        TEXT,
    strength    REAL,
    frequency   TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_collocations_sense ON collocations(sense_id);

-- ============================================================================
-- 6. SENSE TRANSLATIONS  (sense-level; Phase 4)
-- ============================================================================
-- Contract:
--   phonetic_ar  → pronunciations table (word-level, Phase 1)
--   translation  → here (sense-level, Phase 4)
--   transliteration → here; Romanized Arabic TRANSLATION only (never the English word)
--                   Language-specific requirements enforced by Phase 5 QA:
--                   zh, ja  → required (Pinyin / Romaji)
--                   ar      → optional (already in Arabic script)
--                   others  → optional but checked if provided
--
-- State machine:
--   needs_review  → initial
--   valid         → QA passed; translation NOT NULL
--   unavailable   → no direct translation exists; translation IS NULL
--   rejected      → QA found translation is wrong; triggers Phase 7A regeneration
--                   (rejected → needs_review after regen)
-- ============================================================================
CREATE TABLE IF NOT EXISTS sense_translations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sense_id        INTEGER NOT NULL REFERENCES word_senses(id) ON DELETE CASCADE,
    language        TEXT    NOT NULL CHECK (language IN ('ar','fr','de','es','zh','ru','pt','ja','it','tr')),
    translation     TEXT,
    transliteration TEXT,    -- Romanized form of `translation`; NULL allowed
    status          TEXT    DEFAULT 'needs_review'
                    CHECK (status IN ('valid','unavailable','needs_review','rejected')),
    is_primary      INTEGER DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(sense_id, language),
    -- DB-level invariant: valid/needs_review/rejected → translation NOT NULL
    --                     unavailable                 → translation IS NULL
    CHECK (
        (status = 'unavailable' AND translation IS NULL AND transliteration IS NULL) OR
        (status IN ('valid','needs_review','rejected') AND translation IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_translations_sense ON sense_translations(sense_id);
CREATE INDEX IF NOT EXISTS idx_translations_lang  ON sense_translations(language);

-- ============================================================================
-- 7. SENSE RELATIONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS sense_relations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_sense_id INTEGER NOT NULL REFERENCES word_senses(id) ON DELETE CASCADE,
    target_word     TEXT    NOT NULL,
    target_sense_id INTEGER REFERENCES word_senses(id),
    relation_type   TEXT    NOT NULL CHECK (relation_type IN (
                        'synonym','antonym','hypernym','hyponym',
                        'related','confusable','word_family'
                    )),
    confidence      REAL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON sense_relations(source_sense_id);
CREATE INDEX IF NOT EXISTS idx_relations_type   ON sense_relations(relation_type);

-- ============================================================================
-- 8. WORD FAMILIES  (word-level; morphological derivatives)
-- ============================================================================
CREATE TABLE IF NOT EXISTS word_families (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id    INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    noun_form  TEXT    DEFAULT '',
    verb_form  TEXT    DEFAULT '',
    adj_form   TEXT    DEFAULT '',
    adv_form   TEXT    DEFAULT '',
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(word_id)
);

-- ============================================================================
-- 9. LEARNER NOTES  (sense-level)
-- ============================================================================
CREATE TABLE IF NOT EXISTS learner_notes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sense_id       INTEGER NOT NULL REFERENCES word_senses(id) ON DELETE CASCADE,
    note_type      TEXT    NOT NULL CHECK (note_type IN (
                       'common_error','confusable','ielts_tip',
                       'grammar_pattern','preposition_pattern'
                   )),
    incorrect      TEXT,
    correct        TEXT,
    explanation_ar TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================================
-- 10. IELTS METADATA  (word-level; generic relevance only)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ielts_metadata (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id          INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    relevance        REAL,
    topics           TEXT,    -- JSON array
    writing_utility  TEXT    CHECK (writing_utility  IN ('high','medium','low')),
    speaking_utility TEXT    CHECK (speaking_utility IN ('high','medium','low')),
    is_academic      INTEGER DEFAULT 0,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(word_id)
);

-- ============================================================================
-- 11. SOURCE RECORDS  (immutable lineage)
-- ============================================================================
CREATE TABLE IF NOT EXISTS source_records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_db     TEXT    NOT NULL,
    source_table  TEXT    NOT NULL,
    source_row_id INTEGER NOT NULL,
    raw_json      TEXT    NOT NULL,
    source_hash   TEXT    NOT NULL,
    imported_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_db, source_table, source_row_id)
);

-- ============================================================================
-- 13. QA RESULTS  (independent judge; model_self_confidence NOT stored here)
-- ============================================================================
CREATE TABLE IF NOT EXISTS qa_results (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sense_id          INTEGER NOT NULL REFERENCES word_senses(id) ON DELETE CASCADE,
    run_id            INTEGER REFERENCES enrichment_runs(id),
    qa_type           TEXT    NOT NULL CHECK (qa_type IN ('deterministic','llm_judge')),
    score             REAL,
    rubric            TEXT,               -- e.g. "v1"
    judge_model       TEXT,
    judge_prompt_hash TEXT,
    decision          TEXT CHECK (decision IN ('pass','review','fail','regenerate')),
    issues            TEXT,               -- JSON array of issue strings
    details           TEXT,               -- JSON full rubric breakdown
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_qa_sense    ON qa_results(sense_id);
CREATE INDEX IF NOT EXISTS idx_qa_decision ON qa_results(decision);

-- ============================================================================
-- 14. FIELD VERSIONS  (model_self_confidence stored here as untrusted metadata)
-- ============================================================================
CREATE TABLE IF NOT EXISTS field_versions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type           TEXT    NOT NULL,
    entity_id             INTEGER NOT NULL,
    field_name            TEXT    NOT NULL,
    value                 TEXT,
    pipeline_version      TEXT    NOT NULL,
    model                 TEXT,
    model_self_confidence REAL,    -- aiConfidence from model; NOT used for QA decisions
    prompt_hash           TEXT,
    source_hash           TEXT,
    status                TEXT    DEFAULT 'current'
                          CHECK (status IN ('current','superseded','rejected')),
    created_at            TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fv_entity ON field_versions(entity_type, entity_id);

-- ============================================================================
-- 15. WORD EMBEDDINGS  (Phase 8; only after QA pass)
-- ============================================================================
CREATE TABLE IF NOT EXISTS word_embeddings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id           INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    embedding_model   TEXT    NOT NULL,
    embedding_version TEXT,
    vector            BLOB    NOT NULL,
    input_text        TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(word_id, embedding_model)
);

-- ============================================================================
-- 16. EVALUATION RUNS (Batch tracking for Legacy vs V2 comparison)
-- ============================================================================
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_size       INTEGER NOT NULL,
    model             TEXT,
    prompt_hash       TEXT,
    schema_hash       TEXT,
    evaluator_version TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    status            TEXT DEFAULT 'running'
);

-- ============================================================================
-- 17. WORD EVALUATIONS (Field-by-field and overall verdicts)
-- ============================================================================
CREATE TABLE IF NOT EXISTS word_evaluations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES evaluation_runs(id),
    word_id             INTEGER NOT NULL REFERENCES words(id),

    raw_generated_payload TEXT,
    machine_validation_result TEXT, -- e.g., pass, schema_failed, missing_required, invalid_enum, wrong_pos

    structural_score    REAL,
    validity_score      REAL,
    content_completeness REAL,
    preservation_score  REAL,
    loss_score          REAL,    -- 1.0=any field removed from legacy, 0.0=no loss
    
    linguistic_score    REAL,
    pedagogical_score   REAL,
    legacy_quality      REAL,
    generated_quality   REAL,
    improvement_score   REAL,

    decision            TEXT CHECK (decision IN (
        'keep_legacy',
        'enrich',
        'regenerate',
        'manual_review'
    )),
    reason              TEXT,
    field_comparison    TEXT,

    -- Generation Metadata per word
    model               TEXT,
    prompt_hash         TEXT,
    schema_hash         TEXT,
    pipeline_version    TEXT,
    temperature         REAL,
    batch_id            TEXT,
    request_index       INTEGER,
    started_at          TEXT,
    completed_at        TEXT,
    latency_ms          INTEGER,
    input_tokens        INTEGER,
    output_tokens       INTEGER,

    evaluator_version   TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(run_id, word_id)
);

