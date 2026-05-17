from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from app.config import Config
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Create SQLAlchemy engine with pooling
def get_engine() -> Engine:
    try:
        engine = create_engine(
            Config.MYSQL_URL,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=Config.DEBUG_SQL
        )
        return engine
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        raise

engine = get_engine()

def test_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful.")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {e}")
        return False
