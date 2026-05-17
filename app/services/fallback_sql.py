import re
from difflib import get_close_matches
from sqlalchemy import text
from app.database.connection import engine
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

CATEGORIES = {
    "ancient": "Historical",
    "beach": "Beach",
    "family": "Family",
    "historic": "Historical",
    "historical": "Historical",
    "museum": "Museum",
    "museums": "Museum",
    "religious": "Religious",
}

# Regex to detect a clear location intent: "in <word>" or "at <word>"
_LOCATION_INTENT_RE = re.compile(r"\bin\s+\S+|\bat\s+\S+")


def _normalize_question(question: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace."""
    q = question.lower().strip()
    q = re.sub(r"[^\w\s]", " ", q)   # replace punctuation with space
    q = re.sub(r"\s+", " ", q)        # collapse multiple spaces
    return q


class FallbackSQLGenerator:
    """Small deterministic fallback for common tourism searches.

    This keeps the app useful when the LLM provider is unavailable, while still
    returning queries that pass the normal allowlist validator.
    """

    def __init__(self):
        self.governorates = self._load_governorates()

    def _load_governorates(self) -> dict[str, str]:
        gov_map = {}
        try:
            logger.info("Dynamically loading governorates from database...")
            from sqlalchemy import inspect
            with engine.connect() as conn:
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                gov_table = next((t for t in tables if t.lower() == "governorate"), "governorate")

                result = conn.execute(text(f"SELECT GovernorateName FROM `{gov_table}`"))
                rows = result.fetchall()
                for row in rows:
                    name = row[0]
                    cleaned_name = name.strip()
                    lower_name = cleaned_name.lower()

                    # ── Exact form ──────────────────────────────────────────
                    gov_map[lower_name] = cleaned_name

                    # ── Fix 1: Exhaustive separator variants ─────────────────
                    # For "kafr el-sheikh" we generate all 4 combinations of
                    # hyphen ↔ space ↔ nothing so that fully-squished inputs
                    # like "kafrelshiek" are also covered.
                    has_hyphen = "-" in lower_name
                    has_space  = " " in lower_name

                    if has_hyphen or has_space:
                        # Replace every hyphen AND space with nothing (squish)
                        squished = re.sub(r"[-\s]", "", lower_name)
                        # Replace every hyphen AND space with a single space
                        spaced   = re.sub(r"[-\s]+", " ", lower_name)
                        # Replace every space with a hyphen (and collapse double hyphens)
                        hyphenated = re.sub(r"\s+", "-", spaced)

                        for variant in {squished, spaced, hyphenated}:
                            gov_map[variant] = cleaned_name

                    # ── Fix 1 (continued): Phonetic deviations ────────────────
                    # sheikh  ↔ shiekh   (common transposition)
                    # el      ↔ al       (Arabic article variant)
                    phonetic_bases = [lower_name]

                    if "sheikh" in lower_name:
                        phonetic_bases.append(lower_name.replace("sheikh", "shiekh"))
                    if "shiekh" in lower_name:
                        phonetic_bases.append(lower_name.replace("shiekh", "sheikh"))
                    if " el-" in lower_name or " el " in lower_name:
                        phonetic_bases.append(re.sub(r"\bel\b", "al", lower_name))
                    if " al-" in lower_name or " al " in lower_name:
                        phonetic_bases.append(re.sub(r"\bal\b", "el", lower_name))

                    for base in phonetic_bases[1:]:   # skip index 0 (already added)
                        gov_map[base] = cleaned_name
                        squished = re.sub(r"[-\s]", "", base)
                        spaced   = re.sub(r"[-\s]+", " ", base)
                        for v in {squished, spaced}:
                            gov_map[v] = cleaned_name

            logger.info(
                f"Successfully loaded {len(gov_map)} governorate lookup variations from DB."
            )
        except Exception as e:
            # Fallback to hardcoded list if database connection fails
            logger.error(f"Failed to load governorates dynamically from DB: {e}")
            gov_map = {
                "cairo": "Cairo",
                "giza": "Giza",
                "alexandria": "Alexandria",
                "luxor": "Luxor",
                "aswan": "Aswan",
                "south sinai": "South Sinai",
                "southsinai": "South Sinai",
                "north sinai": "North Sinai",
                "northsinai": "North Sinai",
                "red sea": "Red Sea",
                "redsea": "Red Sea",
                "matrouh": "Matrouh",
                "suez": "Suez",
                "ismailia": "Ismailia",
                "port said": "Port Said",
                "portsaid": "Port Said",
                "damietta": "Damietta",
                "dakahlia": "Dakahlia",
                "sharqia": "Sharqia",
                "qalyubia": "Qalyubia",
                "gharbia": "Gharbia",
                # Kafr el-Sheikh — all common spellings / squished variants
                "kafr el-sheikh": "Kafr el-Sheikh",
                "kafr el sheikh": "Kafr el-Sheikh",
                "kafr elsheikh": "Kafr el-Sheikh",
                "kafrelsheikh": "Kafr el-Sheikh",
                "kafr el-shiekh": "Kafr el-Sheikh",
                "kafr el shiekh": "Kafr el-Sheikh",
                "kafr elshiekh": "Kafr el-Sheikh",
                "kafrelshiekh": "Kafr el-Sheikh",
                "kafrelshiek": "Kafr el-Sheikh",
                "kafrelsheik": "Kafr el-Sheikh",
                "monufia": "Monufia",
                "beheira": "Beheira",
                "fayoum": "Fayoum",
                "beni suef": "Beni Suef",
                "benisuef": "Beni Suef",
                "minya": "Minya",
                "asyut": "Asyut",
                "sohag": "Sohag",
                "qena": "Qena",
                "new valley": "New Valley",
                "newvalley": "New Valley",
            }
            
        # Add common abbreviations that aren't phonetic
        abbreviations = {
            "alex": "Alexandria",
            "hurghada": "Red Sea",
            "sharm": "South Sinai",
            "dahab": "South Sinai",
            "masr": "Cairo",
            "el qahira": "Cairo",
        }
        gov_map.update(abbreviations)
        
        return gov_map

    # ─────────────────────────────────────────────────────────────────────────
    # Fix 3: Normalize the question before matching
    # ─────────────────────────────────────────────────────────────────────────
    def generate(self, user_question: str) -> str | None:
        question = _normalize_question(user_question)

        wants_events = "event" in question or "festival" in question
        wants_places = "place" in question or "visit" in question or not wants_events

        # Fix 2 + 5: Try exact/substring match first, then fuzzy fallback
        governorate = self._find_governorate(question)
        category    = self._find_value(question, CATEGORIES)
        max_price   = self._find_price(question)

        logger.info(
            f"Fallback parse — governorate={governorate!r}, "
            f"category={category!r}, max_price={max_price}"
        )

        # Fix 4: If user expressed a clear location intent but we couldn't
        # resolve it, return None so the caller can surface a helpful message
        # rather than silently returning unfiltered (and misleading) results.
        if _LOCATION_INTENT_RE.search(question) and governorate is None and category is None and max_price is None:
            logger.warning(
                f"Unresolved location intent in: {question!r}. "
                "Returning None to avoid misleading results."
            )
            return None

        if wants_events:
            return self._event_query(governorate, category, max_price)
        if wants_places:
            return self._place_query(governorate, category, max_price)
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Fix 2: Longest-match-first substring matching (no word-boundary regex)
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _find_value(question: str, values: dict[str, str]) -> str | None:
        """Return the canonical value for the longest matching token in question."""
        # Sort by token length descending — prefer more-specific matches
        for token, value in sorted(values.items(), key=lambda x: len(x[0]), reverse=True):
            if token in question:
                return value
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Fix 5: Fuzzy matching layer for governorates
    # ─────────────────────────────────────────────────────────────────────────
    def _find_governorate(self, question: str) -> str | None:
        """Resolve a governorate name from the question.

        Strategy (in order):
        1. Exact substring match (longest-key-first) — covers all pre-built variants.
        2. Word-level fuzzy match using difflib — handles novel misspellings that
           weren't enumerated at load time.
        """
        # 1. Exact substring (covers squished + phonetic variants built at load time)
        result = self._find_value(question, self.governorates)
        if result:
            return result

        # 2. Fuzzy match: test every 1-gram, 2-gram, and 3-gram in the question
        #    against all known governorate keys and accept matches ≥ 0.75 similarity.
        all_keys = list(self.governorates.keys())
        words = question.split()
        for n in range(3, 0, -1):
            for i in range(len(words) - n + 1):
                candidate = " ".join(words[i : i + n])
                matches = get_close_matches(candidate, all_keys, n=1, cutoff=0.75)
                if matches:
                    matched_key = matches[0]
                    logger.info(
                        f"Fuzzy match: '{candidate}' -> '{matched_key}' "
                        f"-> '{self.governorates[matched_key]}'"
                    )
                    return self.governorates[matched_key]

        return None

    @staticmethod
    def _find_price(question: str) -> int | None:
        if "free" in question:
            return 0

        price_match = re.search(r"(?:under|below|less than|<=?)\s*(\d+)", question)
        if price_match:
            return int(price_match.group(1))
        return None

    @staticmethod
    def _place_query(
        governorate: str | None, category: str | None, max_price: int | None
    ) -> str:
        select_price  = ", MIN(tp.Price) AS MinPrice" if max_price is not None else ""
        select_rating = ", p.AverageRating" if max_price is None else ""
        joins = [
            "JOIN location l ON p.LocationID = l.LocationID",
            "JOIN area a ON l.AreaID = a.AreaID",
            "JOIN governorate g ON a.GovernorateID = g.GovernorateID",
        ]
        conditions = []

        if category:
            joins.extend([
                "JOIN place_category pc ON p.PlaceID = pc.PlaceID",
                "JOIN category c ON pc.CategoryID = c.CategoryID",
            ])
            conditions.append(f"c.Name = '{category}'")
        if max_price is not None:
            joins.append("JOIN ticket_place tp ON tp.PlaceID = p.PlaceID")
            conditions.append(f"tp.Price <= {max_price}")
        if governorate:
            conditions.append(f"g.GovernorateName = '{governorate}'")

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        group_clause = " GROUP BY p.PlaceID, p.Name, p.Description, g.GovernorateName" if max_price is not None else ""
        order_clause = " ORDER BY MinPrice ASC" if max_price is not None else " ORDER BY p.AverageRating DESC"

        return (
            f"SELECT DISTINCT p.PlaceID, p.Name, p.Description, g.GovernorateName{select_price}{select_rating} "
            f"FROM place p {' '.join(joins)}{where_clause}{group_clause}{order_clause} LIMIT 5"
        )

    @staticmethod
    def _event_query(
        governorate: str | None, category: str | None, max_price: int | None
    ) -> str:
        select_price = ", MIN(te.Price) AS MinPrice" if max_price is not None else ""
        joins = [
            "JOIN location l ON e.LocationID = l.LocationID",
            "JOIN area a ON l.AreaID = a.AreaID",
            "JOIN governorate g ON a.GovernorateID = g.GovernorateID",
        ]
        conditions = []

        if category:
            joins.extend([
                "JOIN event_category ec ON e.EventID = ec.EventID",
                "JOIN category c ON ec.CategoryID = c.CategoryID",
            ])
            conditions.append(f"c.Name = '{category}'")
        if max_price is not None:
            joins.append("JOIN ticket_event te ON te.EventID = e.EventID")
            conditions.append(f"te.Price <= {max_price}")
        if governorate:
            conditions.append(f"g.GovernorateName = '{governorate}'")

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        group_clause = " GROUP BY e.EventID, e.Name, e.Description, e.StartDate, g.GovernorateName" if max_price is not None else ""
        order_clause = " ORDER BY MinPrice ASC" if max_price is not None else " ORDER BY e.StartDate ASC"

        return (
            f"SELECT DISTINCT e.EventID, e.Name, e.Description, e.StartDate, g.GovernorateName{select_price} "
            f"FROM event e {' '.join(joins)}{where_clause}{group_clause}{order_clause} LIMIT 5"
        )
