"""Evidence + quarantine schemas with provenance discipline (ticket 07).

Implements spec sections 2, 3, 6 / wayfinding 09, 10. Defines the
ADDITIVE canonical structures beside legacy data; inserts no legacy
rows, runs no CEFR canonicalization, admits no staging rows.

Structural invariants (locked, tested):
- every evidence row carries source/version/hash/row/operation
  provenance; provenance is append-only (this module exposes INSERT
  helpers only — no UPDATE/DELETE helper exists, asserted in-test).
- snapshot identity immutable: snapshots register once in
  source_snapshot; later inserts reference it, never rewrite it.
- `is_ielts` is a SQL VIEW over approved IELTS evidence: derived-only
  by construction, no independent write path exists.
- quarantine records carry their own technical id, never a lexical
  identity id (quarantine ID != identity ID).
- identities anchor evidence via composite (lemma, pos) keys; one
  identity may hold many IELTS topic rows.
"""

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lexical_identity (
    normalized_lemma TEXT NOT NULL,
    canonical_pos    TEXT NOT NULL CHECK (canonical_pos IN
        ('adj','adv','conj','det','excl','modal','noun','num',
         'prep','pron','verb')),
    PRIMARY KEY (normalized_lemma, canonical_pos)
);

CREATE TABLE IF NOT EXISTS source_snapshot (
    snapshot_id   TEXT PRIMARY KEY,
    source_name   TEXT NOT NULL,
    source_version TEXT,
    snapshot_hash TEXT NOT NULL,
    source_rows   INTEGER,
    imported_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lexical_frequency (
    normalized_lemma TEXT NOT NULL,
    canonical_pos    TEXT NOT NULL,
    source           TEXT NOT NULL DEFAULT 'wordfreq',
    source_version   TEXT NOT NULL,
    lang             TEXT NOT NULL,
    metric           TEXT NOT NULL DEFAULT 'zipf',
    zipf             REAL NOT NULL,
    corpus_id        TEXT,
    observed_at      TEXT NOT NULL,
    PRIMARY KEY (normalized_lemma, canonical_pos,
                 source, source_version, lang, metric),
    FOREIGN KEY (normalized_lemma, canonical_pos)
        REFERENCES lexical_identity (normalized_lemma, canonical_pos)
);

CREATE TABLE IF NOT EXISTS cefr_evidence (
    evidence_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_lemma TEXT NOT NULL,
    canonical_pos    TEXT NOT NULL,
    source           TEXT NOT NULL,
    source_version   TEXT NOT NULL,
    cefr_value       TEXT NOT NULL CHECK (cefr_value IN
        ('A1','A2','B1','B2','C1','C2')),
    observed_at      TEXT NOT NULL,
    FOREIGN KEY (normalized_lemma, canonical_pos)
        REFERENCES lexical_identity (normalized_lemma, canonical_pos)
);

CREATE TABLE IF NOT EXISTS ielts_evidence (
    evidence_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_lemma TEXT NOT NULL,
    canonical_pos    TEXT NOT NULL,
    ielts_row_id     INTEGER NOT NULL,
    source_lemma     TEXT NOT NULL,
    source_pos       TEXT NOT NULL,
    topic            TEXT,
    approved         INTEGER NOT NULL DEFAULT 1 CHECK (approved IN (0,1)),
    source_db        TEXT NOT NULL,
    source_version   TEXT,
    imported_at      TEXT NOT NULL,
    FOREIGN KEY (normalized_lemma, canonical_pos)
        REFERENCES lexical_identity (normalized_lemma, canonical_pos)
);

CREATE VIEW IF NOT EXISTS is_ielts AS
SELECT DISTINCT normalized_lemma, canonical_pos, 1 AS value
FROM ielts_evidence WHERE approved = 1;

CREATE TABLE IF NOT EXISTS quarantine_record (
    record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL CHECK (kind IN ('vintage_727','multiword')),
    original_form   TEXT NOT NULL,
    normalized_form TEXT NOT NULL,
    source_name     TEXT NOT NULL,
    source_row_id   TEXT,
    classification  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'quarantined',
    recorded_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mapping_provenance (
    ielts_row_id     INTEGER PRIMARY KEY,
    source_lemma     TEXT NOT NULL,
    normalized_form  TEXT NOT NULL,
    source_pos       TEXT NOT NULL,
    classification   TEXT NOT NULL CHECK (classification IN
        ('NORMALIZED_LEMMA_POS_EXACT','NORMALIZED_LEMMA_EXACT',
         'SAME_LEMMA_DIFFERENT_POS','MULTIWORD','NEW_SINGLE_WORD',
         'UNRESOLVED_MALFORMED')),
    matched_lemma    TEXT,
    matched_pos      TEXT,
    topic_ref        TEXT,
    decided_at       TEXT NOT NULL
);
"""


def create_schema(connection):
    """Create all additive canonical structures (idempotent)."""
    connection.executescript(SCHEMA_SQL)
    return connection


def register_snapshot(connection, snapshot_id, source_name, snapshot_hash,
                      imported_at, source_version=None, source_rows=None):
    connection.execute(
        "INSERT INTO source_snapshot "
        "(snapshot_id, source_name, source_version, snapshot_hash,"
        " source_rows, imported_at) VALUES (?,?,?,?,?,?)",
        (snapshot_id, source_name, source_version, snapshot_hash,
         source_rows, imported_at),
    )


def add_identity(connection, normalized_lemma, canonical_pos):
    connection.execute(
        "INSERT OR IGNORE INTO lexical_identity "
        "(normalized_lemma, canonical_pos) VALUES (?,?)",
        (normalized_lemma, canonical_pos),
    )


def add_frequency(connection, lemma, pos, source_version, lang, zipf,
                  observed_at, source="wordfreq", metric="zipf",
                  corpus_id=None):
    connection.execute(
        "INSERT INTO lexical_frequency (normalized_lemma, canonical_pos,"
        " source, source_version, lang, metric, zipf, corpus_id,"
        " observed_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (lemma, pos, source, source_version, lang, metric, zipf,
         corpus_id, observed_at),
    )


def add_cefr_evidence(connection, lemma, pos, source, source_version,
                      cefr_value, observed_at):
    connection.execute(
        "INSERT INTO cefr_evidence (normalized_lemma, canonical_pos,"
        " source, source_version, cefr_value, observed_at)"
        " VALUES (?,?,?,?,?,?)",
        (lemma, pos, source, source_version, cefr_value, observed_at),
    )


def add_ielts_evidence(connection, lemma, pos, ielts_row_id, source_lemma,
                       source_pos, imported_at, topic=None, approved=1,
                       source_db="IeltsWord.db", source_version=None):
    connection.execute(
        "INSERT INTO ielts_evidence (normalized_lemma, canonical_pos,"
        " ielts_row_id, source_lemma, source_pos, topic, approved,"
        " source_db, source_version, imported_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (lemma, pos, ielts_row_id, source_lemma, source_pos, topic,
         approved, source_db, source_version, imported_at),
    )


def add_quarantine(connection, kind, original_form, normalized_form,
                   source_name, classification, recorded_at,
                   source_row_id=None, status="quarantined"):
    connection.execute(
        "INSERT INTO quarantine_record (kind, original_form,"
        " normalized_form, source_name, source_row_id, classification,"
        " status, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
        (kind, original_form, normalized_form, source_name,
         source_row_id, classification, status, recorded_at),
    )


def add_mapping_provenance(connection, ielts_row_id, source_lemma,
                           normalized_form, source_pos, classification,
                           decided_at, matched_lemma=None,
                           matched_pos=None, topic_ref=None):
    connection.execute(
        "INSERT INTO mapping_provenance (ielts_row_id, source_lemma,"
        " normalized_form, source_pos, classification, matched_lemma,"
        " matched_pos, topic_ref, decided_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (ielts_row_id, source_lemma, normalized_form, source_pos,
         classification, matched_lemma, matched_pos, topic_ref,
         decided_at),
    )
