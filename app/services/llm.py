from openai import APIStatusError, AuthenticationError, OpenAI
from app.config import Config
from app.utils.logger import setup_logger
import time

logger = setup_logger(__name__)

class LLMServiceError(RuntimeError):
    """Raised when the configured LLM provider cannot complete a request."""

class LLMAuthError(LLMServiceError):
    """Raised for API key/authentication or account billing failures."""

class MiniMaxService:
    def __init__(self):
        api_key = Config.MINIMAX_API_KEY
        if not api_key:
            logger.warning("MINIMAX_API_KEY is not set. MiniMax calls will fail.")
            
        self.client = OpenAI(
            api_key=api_key or "dummy_key",
            base_url=Config.MINIMAX_BASE_URL
        )
        self._circuit_open_until = 0
        
    def generate_completion(self, system_prompt: str, user_prompt: str, model=None, temperature=0.0, max_retries=3) -> str:
        """Generates a response from MiniMax with retry logic and a circuit breaker."""
        if time.time() < self._circuit_open_until:
            raise LLMAuthError("LLM circuit breaker is open due to recent billing/auth failure. Fast-failing.")

        selected_model = model or Config.MINIMAX_MODEL
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=selected_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=1000
                )
                
                # Log token usage
                if hasattr(response, 'usage'):
                    logger.info(f"Token usage - Prompt: {response.usage.prompt_tokens}, Completion: {response.usage.completion_tokens}")
                    
                return response.choices[0].message.content
                    
            except (AuthenticationError, APIStatusError) as e:
                logger.error(f"MiniMax API call failed on attempt {attempt + 1}: {e}")
                status_code = getattr(e, "status_code", None)
                if status_code in {401, 402, 429}:
                    self._circuit_open_until = time.time() + 60
                    raise LLMAuthError(
                        f"MiniMax authentication or billing failed (Code: {status_code}). Check MINIMAX_API_KEY and account balance."
                    ) from e
                if attempt == max_retries - 1:
                    raise LLMServiceError("MiniMax API request failed.") from e
                time.sleep(2 ** attempt) # Exponential backoff
            except Exception as e:
                logger.error(f"MiniMax API call failed on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise LLMServiceError("MiniMax API request failed.") from e
                time.sleep(2 ** attempt) # Exponential backoff
        return ""
