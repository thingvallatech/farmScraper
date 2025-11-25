"""
Database connection and session management
"""
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from contextlib import contextmanager
from typing import Optional, Any, Dict, List
import logging
from src.config import settings

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages PostgreSQL database connections"""

    def __init__(self):
        self.connection_params = {
            'dbname': settings.postgres_db,
            'user': settings.postgres_user,
            'password': settings.postgres_password,
            'host': settings.postgres_host,
            'port': settings.postgres_port,
        }
        self._connection: Optional[psycopg2.extensions.connection] = None

    def connect(self) -> psycopg2.extensions.connection:
        """Establish database connection"""
        try:
            self._connection = psycopg2.connect(**self.connection_params)
            logger.info("Database connection established")
            return self._connection
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            logger.info("Database connection closed")
            self._connection = None

    @contextmanager
    def get_cursor(self, dict_cursor: bool = True):
        """
        Context manager for database cursor

        Args:
            dict_cursor: If True, return dict-like rows; otherwise return tuples
        """
        conn = self._connection or self.connect()
        cursor_factory = RealDictCursor if dict_cursor else None

        try:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()

    def execute(self, query: str, params: Optional[tuple] = None) -> None:
        """Execute a query without returning results"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)

    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict]:
        """Fetch a single row"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """Fetch all rows"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def insert(self, table: str, data: Dict[str, Any]) -> Optional[int]:
        """
        Insert a row and return the ID

        Args:
            table: Table name
            data: Dictionary of column: value pairs

        Returns:
            ID of inserted row if applicable
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))

        # Convert dict/list values to Json for JSONB columns
        values = []
        for v in data.values():
            if isinstance(v, (dict, list)):
                values.append(Json(v))
            else:
                values.append(v)
        values = tuple(values)

        query = f"""
            INSERT INTO {table} ({columns})
            VALUES ({placeholders})
            RETURNING id
        """

        with self.get_cursor() as cursor:
            cursor.execute(query, values)
            result = cursor.fetchone()
            return result['id'] if result else None

    def update(self, table: str, data: Dict[str, Any], where: str, where_params: tuple) -> int:
        """
        Update rows in table

        Args:
            table: Table name
            data: Dictionary of column: value pairs to update
            where: WHERE clause (without 'WHERE' keyword)
            where_params: Parameters for WHERE clause

        Returns:
            Number of rows updated
        """
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])

        # Convert dict/list values to Json for JSONB columns
        converted_values = []
        for v in data.values():
            if isinstance(v, (dict, list)):
                converted_values.append(Json(v))
            else:
                converted_values.append(v)

        values = tuple(converted_values) + where_params

        query = f"""
            UPDATE {table}
            SET {set_clause}
            WHERE {where}
        """

        with self.get_cursor() as cursor:
            cursor.execute(query, values)
            return cursor.rowcount

    def upsert_raw_page(self, url: str, **kwargs) -> int:
        """Insert or update a raw page record"""
        query = """
            INSERT INTO raw_pages (url, domain, status_code, page_title, raw_html, raw_text, links, metadata)
            VALUES (%(url)s, %(domain)s, %(status_code)s, %(page_title)s, %(raw_html)s, %(raw_text)s, %(links)s, %(metadata)s)
            ON CONFLICT (url) DO UPDATE SET
                scrape_timestamp = NOW(),
                status_code = EXCLUDED.status_code,
                page_title = EXCLUDED.page_title,
                raw_html = EXCLUDED.raw_html,
                raw_text = EXCLUDED.raw_text,
                links = EXCLUDED.links,
                metadata = EXCLUDED.metadata
            RETURNING id
        """

        params = {
            'url': url,
            'domain': kwargs.get('domain'),
            'status_code': kwargs.get('status_code'),
            'page_title': kwargs.get('page_title'),
            'raw_html': kwargs.get('raw_html'),
            'raw_text': kwargs.get('raw_text'),
            'links': Json(kwargs.get('links', {})),
            'metadata': Json(kwargs.get('metadata', {})),
        }

        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result['id']

    def upsert_program(self, **kwargs) -> int:
        """Insert or update a program record"""
        query = """
            INSERT INTO programs (
                program_code, program_name, source_url, description,
                eligibility_raw, eligibility_parsed, payment_info_raw,
                payment_formula, payment_range_text, payment_min, payment_max,
                payment_unit, application_start, application_end, deadline_text,
                confidence_score, extraction_warnings
            )
            VALUES (
                %(program_code)s, %(program_name)s, %(source_url)s, %(description)s,
                %(eligibility_raw)s, %(eligibility_parsed)s, %(payment_info_raw)s,
                %(payment_formula)s, %(payment_range_text)s, %(payment_min)s, %(payment_max)s,
                %(payment_unit)s, %(application_start)s, %(application_end)s, %(deadline_text)s,
                %(confidence_score)s, %(extraction_warnings)s
            )
            ON CONFLICT (program_code, source_url) DO UPDATE SET
                last_updated = NOW(),
                program_name = EXCLUDED.program_name,
                description = EXCLUDED.description,
                eligibility_raw = EXCLUDED.eligibility_raw,
                eligibility_parsed = EXCLUDED.eligibility_parsed,
                payment_info_raw = EXCLUDED.payment_info_raw,
                payment_formula = EXCLUDED.payment_formula,
                payment_range_text = EXCLUDED.payment_range_text,
                payment_min = EXCLUDED.payment_min,
                payment_max = EXCLUDED.payment_max,
                payment_unit = EXCLUDED.payment_unit,
                application_start = EXCLUDED.application_start,
                application_end = EXCLUDED.application_end,
                deadline_text = EXCLUDED.deadline_text,
                confidence_score = EXCLUDED.confidence_score,
                extraction_warnings = EXCLUDED.extraction_warnings
            RETURNING id
        """

        params = {k: Json(v) if k in ('eligibility_parsed', 'extraction_warnings') and v else v
                  for k, v in kwargs.items()}

        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result['id']


# Global database instance
db = DatabaseConnection()
