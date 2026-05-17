from app.services.llm import MiniMaxService
from app.services.query_cache import get_cached_response, set_cached_response
from app.prompts.templates import RESPONSE_FORMATTING_PROMPT
from app.utils.logger import setup_logger
import pandas as pd

logger = setup_logger(__name__)

class ResponseFormatter:
    def __init__(self, llm_service: MiniMaxService):
        self.llm_service = llm_service

    def format_response(self, user_question: str, df: pd.DataFrame) -> str:
        """Takes db results and uses LLM to format a natural language response.

        Pipeline:
        1. Response cache — return instantly if exact question was answered before
        2. LLM formatting — rich, personalised answer
        3. Conversational template fallback — if LLM is unavailable
        """
        if df.empty:
            return (
                "I couldn't find any places or events matching your criteria. "
                "Try a different city or remove some filters!"
            )

        # 1. Response cache check
        cached = get_cached_response(user_question)
        if cached:
            logger.info("Response cache HIT")
            return cached

        # Convert df to JSON for the LLM prompt (limit to top 5 rows)
        limited_df = df.head(5)
        results_json = limited_df.to_json(orient="records")

        system_prompt = RESPONSE_FORMATTING_PROMPT.format(
            user_question=user_question,
            db_results=results_json,
        )

        logger.info("Formatting response using LLM...")
        try:
            response = self.llm_service.generate_completion(
                system_prompt=system_prompt,
                user_prompt="Please summarize the findings naturally.",
                temperature=0.3,
            )
            set_cached_response(user_question, response)
            return response
        except Exception as e:
            logger.error(f"Response formatting failed: {e}")
            # Conversational template — no LLM needed
            response = self._format_conversational(limited_df)
            set_cached_response(user_question, response)
            return response

    @staticmethod
    def _format_conversational(df: pd.DataFrame) -> str:
        """Human-like response without LLM dependency."""
        is_events = "EventID" in df.columns
        entity = "events" if is_events else "places"

        # Extract location from results if available
        location = None
        if "GovernorateName" in df.columns:
            location = df["GovernorateName"].iloc[0]

        # Build opening line
        if location:
            opening = f"Here are some {entity} in **{location}** you might enjoy: 🐪✨"
        else:
            opening = f"Here are some {entity} I found for you: 🐪✨"

        # Build bullet list
        lines = [opening, ""]
        for _, row in df.iterrows():
            name = row.get("Name", "Unknown")
            desc = row.get("Description") if "Description" in df.columns else None
            rating = row.get("AverageRating")
            price = row.get("MinPrice")
            
            detail_parts = []
            if rating and str(rating).lower() not in ("nan", "none", "0"):
                detail_parts.append(f"⭐ {rating}/5")
            if price is not None and str(price).lower() not in ("nan", "none"):
                detail_parts.append(f"💰 {int(price)} EGP")
            
            detail = f" — {', '.join(detail_parts)}" if detail_parts else ""
            
            # Format description text briefly
            desc_text = ""
            if desc and str(desc).lower() not in ("nan", "none"):
                # Truncate to first sentence or ~100 chars
                desc_short = str(desc).split('.')[0]
                if len(desc_short) > 100:
                    desc_short = desc_short[:97] + "..."
                desc_text = f"\n  _{desc_short}_"
                
            lines.append(f"- **{name}**{detail}{desc_text}")

        # Add follow-up suggestions
        lines.extend([
            "",
            "Want me to narrow it down? I can filter by:",
            "- 💰 Budget range",
            "- 🏛️ Historical, Beach, or Family categories",
            "- ⭐ Highly-rated places",
        ])

        return "\n".join(lines)
