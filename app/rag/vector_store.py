import faiss
import numpy as np
import pickle
import os
from pathlib import Path
from app.config import Config
from app.rag.embeddings import EmbeddingService
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Basic schema and examples to initialize the vector store
INITIAL_CHUNKS = [
    {"type": "schema", "content": "Table PLACE: contains PlaceID, Name, Description, LocationID, AverageRating. Represents a tourism destination."},
    {"type": "schema", "content": "Table EVENT: contains EventID, Name, Description, LocationID, StartDate, EndDate. Represents a tourism event."},
    {"type": "schema", "content": "Table LOCATION: contains LocationID, AreaID, Latitude, Longitude. Represents geographical points."},
    {"type": "schema", "content": "Table AREA: contains AreaID, Name, GovernorateID. links to GOVERNORATE."},
    {"type": "schema", "content": "Table GOVERNORATE: contains GovernorateID, GovernorateName. e.g. 'Cairo', 'Giza', 'Luxor', 'Alexandria'."},
    {"type": "schema", "content": "Table CATEGORY: contains CategoryID, Name. e.g. 'Historical', 'Beach', 'Family'."},
    {"type": "schema", "content": "Table TICKET_PLACE: contains TicketID, PlaceID, Price. Use this to find the price of a place."},
    {"type": "schema", "content": "Table TICKET_EVENT: contains TicketID, EventID, Price. Use this to find the price of an event."},
    {"type": "schema", "content": "Table PLACE_CATEGORY: links PlaceID to CategoryID."},
    {"type": "schema", "content": "Table EVENT_CATEGORY: links EventID to CategoryID."},
    {"type": "sql_example", "content": "Question: 'places in Cairo under 500'\nSQL: SELECT DISTINCT p.PlaceID, p.Name, MIN(tp.Price) AS MinPrice FROM PLACE p JOIN LOCATION l ON p.LocationID = l.LocationID JOIN AREA a ON l.AreaID = a.AreaID JOIN GOVERNORATE g ON a.GovernorateID = g.GovernorateID JOIN TICKET_PLACE tp ON tp.PlaceID = p.PlaceID WHERE g.GovernorateName = 'Cairo' AND tp.Price < 500 GROUP BY p.PlaceID, p.Name ORDER BY MinPrice ASC LIMIT 50;"},
    {"type": "sql_example", "content": "Question: 'historical places in Luxor'\nSQL: SELECT DISTINCT p.PlaceID, p.Name FROM PLACE p JOIN PLACE_CATEGORY pc ON p.PlaceID = pc.PlaceID JOIN CATEGORY c ON pc.CategoryID = c.CategoryID JOIN LOCATION l ON p.LocationID = l.LocationID JOIN AREA a ON l.AreaID = a.AreaID JOIN GOVERNORATE g ON a.GovernorateID = g.GovernorateID WHERE c.Name = 'Historical' AND g.GovernorateName = 'Luxor' LIMIT 50;"},
    {"type": "synonym", "content": "Synonyms: 'cheap' usually means price is low. 'free' means price = 0 or no ticket required. 'weekend' means filtering events by upcoming weekend dates."},
]

class VectorStore:
    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service
        self.index_path = Path(Config.FAISS_INDEX_PATH)
        self.index_file = self.index_path / "index.faiss"
        self.meta_file = self.index_path / "meta.pkl"
        self.index = None
        self.metadata = []
        
        self.index_path.mkdir(exist_ok=True)
        self.load_or_create_index()

    def load_or_create_index(self):
        if self.index_file.exists() and self.meta_file.exists():
            logger.info("Loading existing FAISS index...")
            self.index = faiss.read_index(str(self.index_file))
            with open(self.meta_file, "rb") as f:
                self.metadata = pickle.load(f)
        else:
            logger.info("Creating new FAISS index and populating with initial schema...")
            # Determine embedding dimension
            dummy_emb = self.embedding_service.embed_text("test")
            dim = len(dummy_emb)
            self.index = faiss.IndexFlatL2(dim)
            self.add_texts([c["content"] for c in INITIAL_CHUNKS], INITIAL_CHUNKS)
            self.save_index()

    def add_texts(self, texts: list[str], metadata: list[dict]):
        embeddings = self.embedding_service.embed_batch(texts)
        self.index.add(np.array(embeddings).astype('float32'))
        self.metadata.extend(metadata)

    def save_index(self):
        faiss.write_index(self.index, str(self.index_file))
        with open(self.meta_file, "wb") as f:
            pickle.dump(self.metadata, f)

    def search(self, query: str, k: int = 5) -> list[str]:
        """Searches the vector store and returns relevant contexts."""
        query_emb = self.embedding_service.embed_text(query)
        # Reshape to (1, dim)
        query_emb = np.array([query_emb]).astype('float32')
        
        distances, indices = self.index.search(query_emb, k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.metadata):
                results.append(self.metadata[idx]["content"])
        
        return results
