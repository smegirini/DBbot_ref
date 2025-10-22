"""
User Models
사용자 관련 Pydantic 모델
"""
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from .base import TimestampMixin


class UserBase(BaseModel):
    """사용자 기본 모델"""
    username: str = Field(min_length=2, max_length=50, description='사용자 이름')
    email: Optional[EmailStr] = Field(default=None, description='이메일')
    kakao_id: Optional[str] = Field(default=None, max_length=100, description='카카오톡 ID')
    is_active: bool = Field(default=True, description='활성 상태')


class UserCreate(UserBase):
    """사용자 생성 요청 모델"""
    password: str = Field(min_length=8, max_length=100, description='비밀번호')


class UserUpdate(BaseModel):
    """사용자 수정 요청 모델"""
    username: Optional[str] = Field(default=None, min_length=2, max_length=50)
    email: Optional[EmailStr] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class UserInDB(UserBase, TimestampMixin):
    """데이터베이스 사용자 모델"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='사용자 ID')
    hashed_password: str = Field(description='해시된 비밀번호')


class UserResponse(UserBase):
    """사용자 응답 모델 (비밀번호 제외)"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='사용자 ID')
    created_at: Optional[str] = Field(default=None, description='생성 시간')


class UserLogin(BaseModel):
    """로그인 요청 모델"""
    username: str = Field(description='사용자 이름')
    password: str = Field(description='비밀번호')
