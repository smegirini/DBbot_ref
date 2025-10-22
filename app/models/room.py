"""
Room Models
카카오톡 방 관련 Pydantic 모델
"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from .base import TimestampMixin


class RoomBase(BaseModel):
    """방 기본 모델"""
    room_name: str = Field(min_length=1, max_length=100, description='방 이름')
    room_type: str = Field(default='group', description='방 유형: private, group, open')
    description: Optional[str] = Field(default=None, max_length=500, description='방 설명')
    is_active: bool = Field(default=True, description='활성 상태')


class RoomCreate(RoomBase):
    """방 생성 요청 모델"""
    kakao_room_id: Optional[str] = Field(default=None, max_length=100, description='카카오톡 방 ID')


class RoomUpdate(BaseModel):
    """방 수정 요청 모델"""
    room_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = Field(default=None)


class RoomInDB(RoomBase, TimestampMixin):
    """데이터베이스 방 모델"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='방 ID')
    kakao_room_id: Optional[str] = Field(default=None, description='카카오톡 방 ID')


class RoomResponse(RoomInDB):
    """방 응답 모델"""
    member_count: Optional[int] = Field(default=0, description='멤버 수')


class RoomMember(BaseModel):
    """방 멤버 모델"""
    model_config = ConfigDict(from_attributes=True)

    room_id: int = Field(description='방 ID')
    user_id: int = Field(description='사용자 ID')
    role: str = Field(default='member', description='역할: admin, member')
    joined_at: Optional[str] = Field(default=None, description='가입 시간')
