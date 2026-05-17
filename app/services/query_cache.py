"""
query_cache.py — In-memory LRU cache for the Kemet chatbot pipeline.

Two independent caches:
  - SQL cache  : normalized question → generated SQL string
  - Response cache : normalized question → final formatted response string

Both use functools.lru_cache under the hood via a thin wrapper so the cache
survives the lifetime of the Streamlit process (which is a single Python process
kept alive by @st.cache_resource).

Thread safety: lru_cache on a free function is GIL-protected; the Streamlit
main thread is single-threaded per session so this is safe in practice.
"""

import re
from functools import lru_cache
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

_SQL_CACHE_SIZE = 256      # unique questions → SQL strings
_RESP_CACHE_SIZE = 128     # unique questions → formatted responses


def _normalize_key(question: str) -> str:
    """Produce a stable cache key from a user question.

    - Lowercase
    - Strip leading/trailing whitespace
    - Collapse internal whitespace to single spaces
    - Remove punctuation that doesn't change meaning
    """
    key = question.lower().strip()
    key = re.sub(r"[^\w\s]", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key


# ── SQL cache ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=_SQL_CACHE_SIZE)
def _sql_cache_get(key: str) -> str | None:
    # lru_cache stores the RETURN VALUE — we use a sentinel pattern instead.
    # This function should never be called directly; use the wrapper below.
    return None  # pragma: no cover


# We can't store mutable values inside lru_cache easily, so we maintain a
# plain dict for the actual storage and use lru_cache only for key eviction
# tracking.  A simple dict with maxsize logic is cleaner here.

class _LRUDict:
    """A simple dict-based LRU cache with a max size and hit/miss counters."""

    def __init__(self, maxsize: int, name: str):
        self._cache: dict[str, str] = {}
        self._maxsize = maxsize
        self._name = name
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> str | None:
        value = self._cache.get(key)
        if value is not None:
            self.hits += 1
            # Move to end (most-recently-used)
            self._cache[key] = self._cache.pop(key)
            logger.debug(f"[{self._name}] Cache HIT for key: {key!r}")
            return value
        self.misses += 1
        return None

    def set(self, key: str, value: str) -> None:
        if key in self._cache:
            self._cache.pop(key)
        elif len(self._cache) >= self._maxsize:
            # Evict the least-recently-used (first inserted) entry
            evicted = next(iter(self._cache))
            del self._cache[evicted]
            logger.debug(f"[{self._name}] Evicted LRU key: {evicted!r}")
        self._cache[key] = value

    def stats(self) -> dict:
        total = self.hits + self.misses
        rate = (self.hits / total * 100) if total else 0.0
        return {
            "name": self._name,
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(rate, 1),
        }

    def clear(self) -> None:
        self._cache.clear()
        self.hits = 0
        self.misses = 0


# Module-level singletons — shared across the Streamlit process lifetime
_sql_cache  = _LRUDict(_SQL_CACHE_SIZE,  "SQL")
_resp_cache = _LRUDict(_RESP_CACHE_SIZE, "Response")


# ── Public API ─────────────────────────────────────────────────────────────────

def get_cached_sql(question: str) -> str | None:
    """Return cached SQL for *question*, or None if not cached."""
    return _sql_cache.get(_normalize_key(question))


def set_cached_sql(question: str, sql: str) -> None:
    """Store *sql* under the normalized *question* key."""
    _sql_cache.set(_normalize_key(question), sql)
    logger.info(f"[SQL cache] Stored SQL for: {_normalize_key(question)!r}")


def get_cached_response(question: str) -> str | None:
    """Return cached formatted response for *question*, or None."""
    return _resp_cache.get(_normalize_key(question))


def set_cached_response(question: str, response: str) -> None:
    """Store *response* under the normalized *question* key."""
    _resp_cache.set(_normalize_key(question), response)
    logger.info(f"[Response cache] Stored response for: {_normalize_key(question)!r}")


def cache_stats() -> dict:
    """Return hit/miss statistics for both caches (useful for debug logging)."""
    return {
        "sql": _sql_cache.stats(),
        "response": _resp_cache.stats(),
    }


def clear_all_caches() -> None:
    """Clear both caches (e.g., after a DB schema change)."""
    _sql_cache.clear()
    _resp_cache.clear()
    logger.warning("All query caches cleared.")
