from app.services.fallback_sql import FallbackSQLGenerator
from app.services.llm import LLMServiceError, MiniMaxService
from app.services.query_cache import get_cached_sql, set_cached_sql, cache_stats
from app.services.query_classifier import classify, QueryIntent
from app.rag.vector_store import VectorStore
from app.sql.validator import SQLValidator
from app.prompts.templates import SQL_GENERATION_PROMPT
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class TextToSQLService:
    def __init__(
        self,
        llm_service: MiniMaxService,
        vector_store: VectorStore,
        sql_validator: SQLValidator,
    ):
        self.llm_service = llm_service
        self.vector_store = vector_store
        self.sql_validator = sql_validator
        self.fallback_sql = FallbackSQLGenerator()

    def generate_sql(self, user_question: str) -> str:
        """Generates and validates SQL from a natural language question.

        Pipeline (in order):
        1. SQL cache    — return instantly if question was seen before
        2. Deterministic fast-path (FallbackSQLGenerator)
           — handles SIMPLE queries without any LLM or embedding call
        3. LLM + RAG    — only for COMPLEX queries that the fallback can't cover
        """
        logger.info(f"Generating SQL for: {user_question}")

        # ── 1. Cache check ────────────────────────────────────────────────────
        cached = get_cached_sql(user_question)
        if cached:
            logger.info(f"SQL cache HIT — stats: {cache_stats()['sql']}")
            return cached

        # ── 2. Deterministic fast-path ────────────────────────────────────────
        intent = classify(user_question)

        if intent in (QueryIntent.SIMPLE, QueryIntent.GREETING):
            fallback_query = self.fallback_sql.generate(user_question)
            if fallback_query and self.sql_validator.is_valid_select(fallback_query):
                logger.info(f"Deterministic path — SQL: {fallback_query}")
                set_cached_sql(user_question, fallback_query)
                return fallback_query
            # If fallback returned None (unresolved location) and this is
            # classified SIMPLE, there's nothing meaningful the LLM can add
            # either — surface a helpful error instead.
            if fallback_query is None:
                raise ValueError(
                    "Could not resolve the location in your query. "
                    "Please try a known Egyptian city or governorate."
                )

        # ── 3. LLM + RAG path (COMPLEX queries only) ─────────────────────────
        # Skip the FAISS search entirely for simple queries — we only reach
        # this code for genuinely complex, open-ended questions.
        relevant_chunks = self.vector_store.search(user_question, k=5)
        schema_context = "\n".join(relevant_chunks)

        system_prompt = SQL_GENERATION_PROMPT.format(
            schema_context=schema_context,
            user_question=user_question,
        )

        try:
            raw_response = self.llm_service.generate_completion(
                system_prompt=system_prompt,
                user_prompt=f"Generate SQL for: {user_question}",
                temperature=0.0,
            )
        except LLMServiceError as e:
            # LLM is down — try the fallback as a last resort even for complex queries
            logger.warning(f"LLM failed for COMPLEX query, attempting fallback: {e}")
            fallback_query = self.fallback_sql.generate(user_question)
            if fallback_query and self.sql_validator.is_valid_select(fallback_query):
                logger.info(f"Fallback SQL (LLM down): {fallback_query}")
                set_cached_sql(user_question, fallback_query)
                return fallback_query
            raise

        # Clean and validate the LLM output
        cleaned_sql = self.sql_validator.sanitize_query(raw_response)
        logger.info(f"LLM-generated SQL: {cleaned_sql}")

        if self.sql_validator.is_valid_select(cleaned_sql):
            set_cached_sql(user_question, cleaned_sql)
            return cleaned_sql

        logger.error(f"Validation failed for LLM SQL: {cleaned_sql}")
        raise ValueError("Generated SQL failed safety validation or is not a SELECT query.")
