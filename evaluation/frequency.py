"""Versioned frequency observations + dense rank (build ticket 06).

Implements spec section 2 (frequency) / wayfinding 01. Pure functions
over in-memory mappings; no I/O, no network, no DB access, no live
wordfreq fetching (live sourcing belongs to execution scope; this
ticket locks recording + derivation, verified on pinned fixtures).

Rules:
- one observation = one identity key + one pinned source/version.
- rank derives per pinned (source, source_version, lang, metric) set
  by descending Zipf; equal Zipf shares the dense rank.
- alphabetical normalized_lemma orders display within equal-rank
  groups only; derivation is independent of input order.
- legacy rank/frequency columns are never read, written, or consumed
  here (or anywhere new): byte-identical before/after, by construction
  (this module cannot address a database).
"""

from evaluation.utils import utc_now

CANONICAL_SOURCE = "wordfreq"
CANONICAL_METRIC = "zipf"


def build_observation(
    identity_key,
    zipf,
    source_version,
    lang,
    source=CANONICAL_SOURCE,
    metric=CANONICAL_METRIC,
    observed_at=None,
    corpus_id=None,
):
    """Record one versioned frequency observation.

    identity_key: (normalized_lemma, canonical_pos) per BT-04.
    zipf: finite real number. source_version/lang: non-empty pins.
    corpus_id: underlying corpus/model identity where exposed, kept
    as its own field, never conflated with source_version.
    Raises ValueError on any missing pin or non-finite Zipf.
    """
    if (
        not isinstance(identity_key, tuple)
        or len(identity_key) != 2
        or not all(identity_key)
    ):
        raise ValueError("identity_key must be (lemma, pos): %r" % (identity_key,))
    if not isinstance(zipf, (int, float)) or not (
        float("-inf") < float(zipf) < float("inf")
    ):
        raise ValueError("zipf must be a finite number: %r" % (zipf,))
    for name, value in (
        ("source", source),
        ("source_version", source_version),
        ("lang", lang),
        ("metric", metric),
    ):
        if not value:
            raise ValueError("observation missing pin: %s" % name)
    observation = {
        "identity_key": list(identity_key),
        "source": source,
        "source_version": source_version,
        "lang": lang,
        "metric": metric,
        "zipf": float(zipf),
        "observed_at": observed_at or utc_now(),
    }
    if corpus_id is not None:
        observation["corpus_id"] = corpus_id
    return observation


def _version_scope(observation):
    return (
        observation["source"],
        observation["source_version"],
        observation["lang"],
        observation["metric"],
    )


def derive_ranks(observations):
    """Derive dense lexical ranks within ONE pinned version scope.

    Accepts an iterable of observation dicts sharing a single
    (source, source_version, lang, metric) scope; raises ValueError
    on mixed scopes (ranks from different versions must never merge
    silently — see ranks_by_scope). Returns {identity_key_tuple:
    rank} by descending Zipf. Equal Zipf shares one rank; ordering
    within ties is alphabetical lemma for display determinism and
    never affects the value. Independent of input order. A repeated
    (identity, scope) pair resolves to its last observation
    (explicit supersede, keyed and visible).
    """
    observations = list(observations)
    scopes = {_version_scope(obs) for obs in observations}
    if len(scopes) > 1:
        raise ValueError(
            "refusing to merge ranks across scopes: %r" % (scopes,)
        )
    values = {}
    for obs in observations:
        values[tuple(obs["identity_key"])] = float(obs["zipf"])
    ordered = sorted(values.items(), key=lambda kv: (-kv[1], kv[0][0]))
    ranks = {}
    rank = 0
    last_zipf = None
    for key, zipf in ordered:
        if last_zipf is None or zipf != last_zipf:
            rank += 1
            last_zipf = zipf
        ranks[key] = rank
    return ranks


def ranks_by_scope(observations):
    """Partition by version scope, then derive ranks per scope.

    Returns {(source, version, lang, metric): {identity_key: rank}}.
    Upgrades add scopes; historical scopes are never rewritten.
    """
    by_scope = {}
    for obs in observations:
        by_scope.setdefault(_version_scope(obs), []).append(obs)
    return {
        scope: derive_ranks(obs_list) for scope, obs_list in by_scope.items()
    }
