import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
    MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
    MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
    MYSQL_URL = os.getenv("MYSQL_URL", "mysql+pymysql://user:password@localhost:3306/kemet")
    FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_index")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    DEBUG_SQL = os.getenv("DEBUG_SQL", "True").lower() == "true"
