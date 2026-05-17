import pandas as pd
from sqlalchemy import text
from app.database.connection import engine
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class QueryExecutor:
    def execute(self, query: str) -> pd.DataFrame:
        """Executes a valid SQL query and returns results as a DataFrame."""
        try:
            # Using pandas to read SQL with the SQLAlchemy engine
            with engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
            return df
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            # Do not expose internal db errors directly in production, but helpful for debugging
            raise RuntimeError(f"Database execution failed: {str(e)}")
