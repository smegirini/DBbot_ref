"""
Room Repository
방 데이터 접근 계층
"""
from typing import Optional, List
from app.repositories.base import BaseRepository
from app.models.room import RoomInDB


class RoomRepository(BaseRepository[RoomInDB]):
    """방 Repository"""

    @property
    def table_name(self) -> str:
        return "rooms"

    async def find_by_name(self, room_name: str) -> Optional[dict]:
        """
        Find room by name

        Args:
            room_name: Room name

        Returns:
            Optional[dict]: Room data if found
        """
        query = f"SELECT * FROM {self.table_name} WHERE room_name = %s AND is_deleted = 0"
        return await self.db.fetch_one(query, (room_name,))

    async def find_by_kakao_room_id(self, kakao_room_id: str) -> Optional[dict]:
        """
        Find room by Kakao room ID

        Args:
            kakao_room_id: Kakao room ID

        Returns:
            Optional[dict]: Room data if found
        """
        query = f"SELECT * FROM {self.table_name} WHERE kakao_room_id = %s AND is_deleted = 0"
        return await self.db.fetch_one(query, (kakao_room_id,))

    async def find_active_rooms(self) -> List[dict]:
        """
        Find all active rooms

        Returns:
            List[dict]: List of active rooms
        """
        query = f"SELECT * FROM {self.table_name} WHERE is_active = 1 AND is_deleted = 0"
        return await self.db.fetch_all(query)

    async def find_by_type(self, room_type: str) -> List[dict]:
        """
        Find rooms by type

        Args:
            room_type: Room type (private, group, open)

        Returns:
            List[dict]: List of rooms
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE room_type = %s
            AND is_deleted = 0
            ORDER BY created_at DESC
        """
        return await self.db.fetch_all(query, (room_type,))
