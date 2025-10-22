"""
Database Utilities
데이터베이스 연결 및 유틸리티 함수
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import aiomysql
from aiomysql import Pool
import structlog

from app.config import settings

logger = structlog.get_logger()


class DatabaseManager:
    """데이터베이스 연결 풀 관리자"""

    def __init__(self):
        self._pool: Optional[Pool] = None

    async def create_pool(self) -> Pool:
        """
        Create database connection pool

        Returns:
            Pool: Database connection pool
        """
        try:
            self._pool = await aiomysql.create_pool(
                host=settings.database.host,
                port=settings.database.port,
                user=settings.database.user,
                password=settings.database.password,
                db=settings.database.name,
                minsize=1,
                maxsize=settings.database.pool_size,
                pool_recycle=settings.database.pool_recycle,
                connect_timeout=settings.database.connect_timeout,
                autocommit=True,
                echo=settings.app_debug,
            )
            logger.info(
                "database_pool_created",
                pool_size=settings.database.pool_size,
                host=settings.database.host,
                db=settings.database.name
            )
            return self._pool
        except Exception as e:
            logger.error("database_pool_creation_failed", error=str(e))
            raise

    async def close_pool(self):
        """Close database connection pool"""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info("database_pool_closed")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator:
        """
        Get database connection from pool

        Yields:
            Connection: Database connection

        Example:
            async with db_manager.get_connection() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT * FROM events")
                    result = await cursor.fetchall()
        """
        if not self._pool:
            await self.create_pool()

        async with self._pool.acquire() as conn:
            try:
                yield conn
            except Exception as e:
                await conn.rollback()
                logger.error("database_operation_failed", error=str(e))
                raise
            else:
                await conn.commit()

    @asynccontextmanager
    async def get_cursor(self, connection=None):
        """
        Get database cursor

        Args:
            connection: Optional existing connection

        Yields:
            Cursor: Database cursor
        """
        if connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                yield cursor
        else:
            async with self.get_connection() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    yield cursor

    async def execute_with_retry(
        self,
        query: str,
        params: tuple = (),
        max_retries: Optional[int] = None
    ) -> int:
        """
        Execute query with retry logic

        Args:
            query: SQL query
            params: Query parameters
            max_retries: Maximum retry attempts

        Returns:
            int: Number of affected rows
        """
        retries = max_retries or settings.database.max_retries
        last_error = None

        for attempt in range(retries):
            try:
                async with self.get_connection() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(query, params)
                        return cursor.rowcount
            except Exception as e:
                last_error = e
                logger.warning(
                    "database_query_retry",
                    attempt=attempt + 1,
                    max_retries=retries,
                    error=str(e)
                )
                if attempt < retries - 1:
                    await asyncio.sleep(settings.database.retry_delay)

        logger.error("database_query_failed_after_retries", error=str(last_error))
        raise last_error

    async def fetch_one(
        self,
        query: str,
        params: tuple = ()
    ) -> Optional[dict]:
        """
        Fetch one row from database

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Optional[dict]: Single row as dictionary or None
        """
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchone()

    async def fetch_all(
        self,
        query: str,
        params: tuple = ()
    ) -> list[dict]:
        """
        Fetch all rows from database

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            list[dict]: List of rows as dictionaries
        """
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)
                return await cursor.fetchall()

    async def health_check(self) -> bool:
        """
        Check database connection health

        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            result = await self.fetch_one("SELECT 1 as health")
            return result is not None and result.get('health') == 1
        except Exception as e:
            logger.error("database_health_check_failed", error=str(e))
            return False


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> DatabaseManager:
    """
    FastAPI dependency for database access

    Returns:
        DatabaseManager: Database manager instance
    """
    return db_manager
