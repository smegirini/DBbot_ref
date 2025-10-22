"""
User Repository
사용자 데이터 접근 계층
"""
from typing import Optional
from app.repositories.base import BaseRepository
from app.models.user import UserInDB


class UserRepository(BaseRepository[UserInDB]):
    """사용자 Repository"""

    @property
    def table_name(self) -> str:
        return "users"

    async def find_by_username(self, username: str) -> Optional[dict]:
        """
        Find user by username

        Args:
            username: Username

        Returns:
            Optional[dict]: User data if found
        """
        query = f"SELECT * FROM {self.table_name} WHERE username = %s AND is_deleted = 0"
        return await self.db.fetch_one(query, (username,))

    async def find_by_email(self, email: str) -> Optional[dict]:
        """
        Find user by email

        Args:
            email: Email address

        Returns:
            Optional[dict]: User data if found
        """
        query = f"SELECT * FROM {self.table_name} WHERE email = %s AND is_deleted = 0"
        return await self.db.fetch_one(query, (email,))

    async def find_by_kakao_id(self, kakao_id: str) -> Optional[dict]:
        """
        Find user by Kakao ID

        Args:
            kakao_id: Kakao ID

        Returns:
            Optional[dict]: User data if found
        """
        query = f"SELECT * FROM {self.table_name} WHERE kakao_id = %s AND is_deleted = 0"
        return await self.db.fetch_one(query, (kakao_id,))

    async def username_exists(self, username: str) -> bool:
        """
        Check if username exists

        Args:
            username: Username

        Returns:
            bool: True if exists
        """
        query = f"SELECT 1 FROM {self.table_name} WHERE username = %s"
        result = await self.db.fetch_one(query, (username,))
        return result is not None
