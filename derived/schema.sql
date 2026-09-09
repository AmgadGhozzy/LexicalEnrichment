-- Derived-layer DDL (Ticket 21). Lives OUTSIDE the canonical WordsMaster.db.
-- Canonical columns are never redefined here; this schema stores EVIDENCE,
-- curriculum orderings, and run tracking that reference lexical identities
-- by (id, lemma, pos) without copying enrichment payload.
--
-- SEMANTICS NOTE (units.totalWords): the canonical units.totalWords counts
-- DISTINCT LEMMAS per unit (verified: equals count(distinct lower(wordEn))).
-- It is NOT a row count. Derived consumers must use
-- unit_stats.distinct_lemma_count. The canonical column is never renamed.

CREATE TABLE IF NOT EXISTS evidence_observations (
    lexical_id      INTEGER NOT NULL,   -- wordsMaster.id (reference only)
    lemma           TEXT    NOT NULL,
    pos             TEXT    NOT NULL,
    dimension       TEXT    NOT NULL,   -- oxford | ielts | cefr | frequency
    tier            TEXT,               -- e.g. exact_lemma_pos |
                                        -- same_lemma_diff_pos | multiword
    value_json      TEXT    NOT NULL,   -- observation payload (JSON)
    source          TEXT    NOT NULL,   -- e.g. fromOxford:unversioned_legacy_flag
                                        -- | ielts_mapping_v2 | legacy_unverified
    source_version  TEXT,               -- NULL until versioned sources land
    observed_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS curriculum_paths (
    curriculum_id   TEXT    NOT NULL,   -- general_progression |
                                        -- oxford_progression | ielts_progression
    position        INTEGER NOT NULL,   -- 1-based order inside the path
    unit_id         TEXT    NOT NULL,   -- units.unitId (reference only)
    rule            TEXT    NOT NULL,   -- deterministic rule that placed it
    PRIMARY KEY (curriculum_id, position)
);

CREATE TABLE IF NOT EXISTS derived_view_runs (
    manifest_sha256 TEXT    PRIMARY KEY,
    baseline_id     TEXT    NOT NULL,   -- e.g. Baseline-PostMigration-002
    canonical_sha256 TEXT   NOT NULL,   -- WordsMaster.db bytes at build time
    rule_version    TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    verdict         TEXT    NOT NULL    -- PASS | HALT
);
