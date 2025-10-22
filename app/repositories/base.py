"""
Base Repository
모든 Repository의 기본 클래스
"""
from typing import Generic, TypeVar, Optional, List, Type
from abc import ABC, abstractmethod

from app.utils import DatabaseManager, LoggerMixin
from app.models.base import PaginationParams

T = TypeVar('T')


class BaseRepository(ABC, LoggerMixin, Generic[T]):
    """
    Base repository implementing common CRUD operations

    Type parameter T represents the model type
    """

    def __init__(self, db: DatabaseManager):
        """
        Initialize repository

        Args:
            db: Database manager instance
        """
        self.db = db

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Table name for this repository"""
        pass

    async def find_by_id(self, id: int) -> Optional[T]:
        """
        Find record by ID

        Args:
            id: Record ID

        Returns:
            Optional[T]: Record if found, None otherwise
        """
        query = f"SELECT * FROM {self.table_name} WHERE id = %s AND is_deleted = 0"
        result = await self.db.fetch_one(query, (id,))
        return result if result else None

    async def find_all(
        self,
        pagination: Optional[PaginationParams] = None
    ) -> List[dict]:
        """
        Find all records with optional pagination

        Args:
            pagination: Pagination parameters

        Returns:
            List[dict]: List of records
        """
        query = f"SELECT * FROM {self.table_name} WHERE is_deleted = 0"

        if pagination:
            query += f" LIMIT {pagination.limit} OFFSET {pagination.offset}"

        return await self.db.fetch_all(query)

    async def count(self, where_clause: str = "", params: tuple = ()) -> int:
        """
        Count records

        Args:
            where_clause: Optional WHERE clause
            params: Query parameters

        Returns:
            int: Record count
        """
        query = f"SELECT COUNT(*) as count FROM {self.table_name}"

        if where_clause:
            query += f" WHERE {where_clause}"
        else:
            query += " WHERE is_deleted = 0"

        result = await self.db.fetch_one(query, params)
        return result['count'] if result else 0

    async def create(self, data: dict) -> int:
        """
        Create new record

        Args:
            data: Record data

        Returns:
            int: Created record ID
        """
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, tuple(data.values()))
                return cursor.lastrowid

    async def update(self, id: int, data: dict) -> bool:
        """
        Update record

        Args:
            id: Record ID
            data: Updated data

        Returns:
            bool: True if updated, False otherwise
        """
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s"

        values = tuple(data.values()) + (id,)
        rowcount = await self.db.execute_with_retry(query, values)
        return rowcount > 0

    async def delete(self, id: int, soft: bool = True) -> bool:
        """
        Delete record

        Args:
            id: Record ID
            soft: If True, perform soft delete (set is_deleted=1)

        Returns:
            bool: True if deleted, False otherwise
        """
        if soft:
            query = f"UPDATE {self.table_name} SET is_deleted = 1 WHERE id = %s"
        else:
            query = f"DELETE FROM {self.table_name} WHERE id = %s"

        rowcount = await self.db.execute_with_retry(query, (id,))
        return rowcount > 0

    async def exists(self, id: int) -> bool:
        """
        Check if record exists

        Args:
            id: Record ID

        Returns:
            bool: True if exists, False otherwise
        """
        query = f"SELECT 1 FROM {self.table_name} WHERE id = %s AND is_deleted = 0"
        result = await self.db.fetch_one(query, (id,))
        return result is not None
