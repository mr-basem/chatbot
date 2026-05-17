import sqlglot
from sqlglot.errors import ParseError
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class SQLValidator:
    def __init__(self):
        # Allowlist of tables that are safe to query
        self.allowed_tables = {
            'place', 'event', 'ticket_place', 'ticket_event', 
            'location', 'area', 'governorate', 'category', 
            'place_category', 'event_category', 'ticket_category', 'ticket_type'
        }

    def is_valid_select(self, query: str) -> bool:
        """Validates if the query is a safe SELECT query."""
        try:
            # Parse the query using sqlglot (dialect: mysql)
            parsed = sqlglot.parse_one(query, read="mysql")
            
            # Ensure it's a SELECT statement
            if not isinstance(parsed, sqlglot.exp.Select):
                logger.warning("Query is not a SELECT statement.")
                return False

            # Check for any unsafe operations (DELETE, UPDATE, DROP, etc.)
            for node in parsed.walk():
                expression = node[0] if isinstance(node, tuple) else node
                if isinstance(expression, (sqlglot.exp.Delete, sqlglot.exp.Update, sqlglot.exp.Insert, sqlglot.exp.Drop, sqlglot.exp.Create)):
                    logger.warning(f"Unsafe operation found in query: {type(expression)}")
                    return False

            # Check accessed tables against allowlist
            tables = [table.name.lower() for table in parsed.find_all(sqlglot.exp.Table)]
            for table in tables:
                if table and table not in self.allowed_tables:
                    logger.warning(f"Unauthorized table access attempt: {table}")
                    return False

            return True
            
        except ParseError as e:
            logger.error(f"SQL parsing failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during SQL validation: {e}")
            return False

    def sanitize_query(self, query: str) -> str:
        """Removes markdown backticks if present."""
        query = query.strip()
        if query.startswith("```sql"):
            query = query[6:]
        if query.startswith("```"):
            query = query[3:]
        if query.endswith("```"):
            query = query[:-3]
        return query.strip()
