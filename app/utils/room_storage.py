"""
Room Storage using PyKV
영구 저장소 기반 room_name → room_id 매핑
"""
from typing import Optional
from iris.util import PyKV


class RoomStorage:
    """
    PyKV를 사용한 영구 방 매핑 저장소

    봇을 재시작해도 room_name → room_id 매핑이 유지됩니다.
    """

    # PyKV 키 prefix
    KEY_PREFIX = "kakaobot:room_mapping:"

    def __init__(self):
        """Initialize PyKV storage"""
        self.kv = PyKV()

    def save_room(self, room_name: str, room_id: int) -> None:
        """
        방 이름과 ID를 저장

        Args:
            room_name: 방 이름
            room_id: 방 ID (Chat ID)
        """
        key = f"{self.KEY_PREFIX}{room_name}"
        self.kv.put(key, str(room_id))

    def get_room_id(self, room_name: str) -> Optional[int]:
        """
        방 이름으로 room_id 조회

        Args:
            room_name: 방 이름

        Returns:
            int: room_id (찾은 경우)
            None: room_id를 찾지 못한 경우
        """
        key = f"{self.KEY_PREFIX}{room_name}"
        value = self.kv.get(key)

        if value:
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        return None

    def delete_room(self, room_name: str) -> None:
        """
        방 매핑 삭제

        Args:
            room_name: 방 이름
        """
        key = f"{self.KEY_PREFIX}{room_name}"
        self.kv.delete(key)

    def list_all_rooms(self) -> dict:
        """
        저장된 모든 방 매핑 조회

        Returns:
            dict: {room_name: room_id} 형태의 딕셔너리
        """
        all_keys = self.kv.list_keys()
        rooms = {}

        for key in all_keys:
            if key.startswith(self.KEY_PREFIX):
                room_name = key.replace(self.KEY_PREFIX, "")
                room_id = self.get_room_id(room_name)
                if room_id:
                    rooms[room_name] = room_id

        return rooms


# 싱글톤 인스턴스
room_storage = RoomStorage()
