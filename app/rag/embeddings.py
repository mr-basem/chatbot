from sentence_transformers import SentenceTransformer
from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class EmbeddingService:
    def __init__(self):
        logger.info(f"Loading embedding model: {Config.EMBEDDING_MODEL}")
        self.model = SentenceTransformer(Config.EMBEDDING_MODEL)
        
    def embed_text(self, text: str):
        """Generates an embedding for a single text."""
        return self.model.encode(text, normalize_embeddings=True)
        
    def embed_batch(self, texts: list):
        """Generates embeddings for a batch of texts."""
        return self.model.encode(texts, normalize_embeddings=True)
