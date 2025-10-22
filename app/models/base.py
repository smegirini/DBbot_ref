"""
Base Models
공통 기본 모델 정의
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class TimestampMixin(BaseModel):
    """타임스탬프 필드 Mixin"""
    created_at: Optional[datetime] = Field(default=None, description='생성 시간')
    updated_at: Optional[datetime] = Field(default=None, description='수정 시간')


class BaseResponse(BaseModel):
    """기본 응답 모델"""
    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(description='성공 여부')
    message: str = Field(description='응답 메시지')
    data: Optional[dict] = Field(default=None, description='응답 데이터')


class ErrorResponse(BaseModel):
    """에러 응답 모델"""
    success: bool = Field(default=False, description='성공 여부')
    error: str = Field(description='에러 타입')
    message: str = Field(description='에러 메시지')
    details: Optional[dict] = Field(default=None, description='상세 정보')


class PaginationParams(BaseModel):
    """페이지네이션 파라미터"""
    page: int = Field(default=1, ge=1, description='페이지 번호')
    page_size: int = Field(default=20, ge=1, le=100, description='페이지 크기')

    @property
    def offset(self) -> int:
        """Calculate offset for database query"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for database query"""
        return self.page_size


class PaginatedResponse(BaseModel):
    """페이지네이션 응답 모델"""
    items: list = Field(description='항목 목록')
    total: int = Field(description='전체 항목 수')
    page: int = Field(description='현재 페이지')
    page_size: int = Field(description='페이지 크기')
    total_pages: int = Field(description='전체 페이지 수')

    @classmethod
    def create(cls, items: list, total: int, page: int, page_size: int):
        """Create paginated response"""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
