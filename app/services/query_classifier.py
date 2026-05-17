"""
query_classifier.py — Lightweight intent classifier for the Kemet chatbot.

Classifies each incoming user question into one of three intents without
calling any external service:

  SIMPLE   — Can be fully resolved by FallbackSQLGenerator.
              These queries only need SQL filtering — no LLM, no RAG search.
              Examples: "places in cairo", "events in luxor under 200 egp"

  COMPLEX  — Open-ended, comparative, or ambiguous questions that genuinely
              benefit from LLM generation and RAG context retrieval.
              Examples: "best romantic spots in Egypt", "compare pyramids and Luxor temples"

  GREETING — Handled entirely by the greeting handler; skip the pipeline.

The classifier intentionally errs on the side of SIMPLE so that deterministic
queries (the overwhelming majority of real traffic) never hit the LLM.
"""

import re
from enum import Enum, auto
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class QueryIntent(Enum):
    SIMPLE  = auto()   # deterministic SQL path
    COMPLEX = auto()   # LLM + RAG path
    GREETING = auto()  # greeting handler


# ── Signals for SIMPLE queries ────────────────────────────────────────────────
# If the query matches any of these patterns AND contains no COMPLEX signals,
# it is classified as SIMPLE.

_SIMPLE_PATTERNS = [
    r"\bplaces?\b",           # "places", "place"
    r"\bevents?\b",           # "events", "event"
    r"\bvisit\b",             # "visit"
    r"\bticket(s)?\b",        # "tickets"
    r"\bprice(s)?\b",         # "price", "prices"
    r"\bfree\b",              # "free admission"
    r"\bunder\s+\d+",         # "under 200"
    r"\bbelow\s+\d+",         # "below 500"
    r"\bless\s+than\s+\d+",   # "less than 100"
    r"\bbeach(es)?\b",        # "beaches"
    r"\bmuseum(s)?\b",        # "museums"
    r"\bhistor(ical|ic)\b",   # "historical", "historic"
    r"\breligious\b",         # "religious sites"
    r"\bfamily\b",            # "family places"
    r"\bfestival(s)?\b",      # "festivals"
]

_SIMPLE_RE = re.compile("|".join(_SIMPLE_PATTERNS), re.IGNORECASE)

# ── Signals for COMPLEX queries ───────────────────────────────────────────────
# These indicate the user wants reasoning, comparison, or recommendations
# beyond what a SQL filter can provide.

_COMPLEX_PATTERNS = [
    r"\bbest\b",              # "best places"
    r"\brecommend\b",         # "recommend me"
    r"\bsuggest\b",           # "suggest an itinerary"
    r"\bcompare\b",           # "compare X and Y"
    r"\bdifference\b",        # "difference between X and Y"
    r"\bitinerary\b",         # "plan an itinerary"
    r"\bwhat (is|are)\b",     # "what is the Pyramids?"
    r"\btell me about\b",     # "tell me about Karnak"
    r"\bwhy\b",               # "why is this famous?"
    r"\bhow (to|do)\b",       # "how do I get to..."
    r"\bwhen\b",              # "when is the best time to visit?"
    r"\brating\b",            # "which has the best rating"
]

_COMPLEX_RE = re.compile("|".join(_COMPLEX_PATTERNS), re.IGNORECASE)

# ── Greeting signals ──────────────────────────────────────────────────────────

_GREETING_PATTERNS = [
    r"^\s*(hi|hello|hey|salam|marhaba|welcome|greetings)\b",
    r"\bhow are you\b",
    r"\bwho are you\b",
    r"\bwhat is your name\b",
    r"\btell me about yourself\b",
    r"\bwho made you\b",
    r"\bwhat do you do\b",
]

_GREETING_RE = re.compile("|".join(_GREETING_PATTERNS), re.IGNORECASE)


def classify(question: str) -> QueryIntent:
    """Classify *question* and return its QueryIntent.

    Classification order (first match wins):
    1. GREETING  — common greeting / bot-identity patterns
    2. COMPLEX   — reasoning / comparison / explanation patterns
    3. SIMPLE    — location + entity patterns (places, events, tickets)
    4. COMPLEX   — default fallback for everything else
    """
    q = question.strip()

    if _GREETING_RE.search(q):
        intent = QueryIntent.GREETING
    elif _COMPLEX_RE.search(q):
        intent = QueryIntent.COMPLEX
    elif _SIMPLE_RE.search(q):
        intent = QueryIntent.SIMPLE
    else:
        intent = QueryIntent.COMPLEX   # unknown → let the LLM try

    logger.info(f"Query classified as {intent.name}: {q!r}")
    return intent


def is_simple(question: str) -> bool:
    return classify(question) == QueryIntent.SIMPLE


def is_complex(question: str) -> bool:
    return classify(question) == QueryIntent.COMPLEX


def is_greeting(question: str) -> bool:
    return classify(question) == QueryIntent.GREETING
