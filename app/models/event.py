"""
Event Models
일정 관련 Pydantic 모델
"""
from datetime import date, time, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator
from .base import TimestampMixin


class EventBase(BaseModel):
    """일정 기본 모델"""
    title: str = Field(min_length=1, max_length=200, description='일정 제목')
    description: Optional[str] = Field(default=None, max_length=1000, description='일정 설명')
    event_date: date = Field(description='일정 날짜')
    event_time: Optional[time] = Field(default=None, description='일정 시간')
    location: Optional[str] = Field(default=None, max_length=200, description='장소')
    is_all_day: bool = Field(default=False, description='종일 일정 여부')


class EventCreate(EventBase):
    """일정 생성 요청 모델"""
    room_id: Optional[int] = Field(default=None, description='방 ID')
    created_by: str = Field(description='생성자')

    # 과거 날짜 검증 제거 - 과거 일정도 등록 가능하도록 함


class EventUpdate(BaseModel):
    """일정 수정 요청 모델"""
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    event_date: Optional[date] = Field(default=None)
    event_time: Optional[time] = Field(default=None)
    location: Optional[str] = Field(default=None, max_length=200)
    is_all_day: Optional[bool] = Field(default=None)


class EventInDB(EventBase, TimestampMixin):
    """데이터베이스 일정 모델"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='일정 ID')
    room_id: Optional[int] = Field(default=None, description='방 ID')
    created_by: str = Field(description='생성자')
    is_deleted: bool = Field(default=False, description='삭제 여부')


class EventResponse(EventInDB):
    """일정 응답 모델"""
    pass


class EventListParams(BaseModel):
    """일정 목록 조회 파라미터"""
    start_date: Optional[date] = Field(default=None, description='시작 날짜')
    end_date: Optional[date] = Field(default=None, description='종료 날짜')
    room_id: Optional[int] = Field(default=None, description='방 ID')
    created_by: Optional[str] = Field(default=None, description='생성자')
    keyword: Optional[str] = Field(default=None, max_length=100, description='검색 키워드')

    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v: Optional[date], info) -> Optional[date]:
        """Validate end_date is after start_date"""
        if v and info.data.get('start_date') and v < info.data['start_date']:
            raise ValueError('종료 날짜는 시작 날짜보다 이후여야 합니다')
        return v


class EventStatistics(BaseModel):
    """일정 통계 모델"""
    total_events: int = Field(description='전체 일정 수')
    upcoming_events: int = Field(description='다가오는 일정 수')
    past_events: int = Field(description='지난 일정 수')
    events_by_month: dict[str, int] = Field(description='월별 일정 수')
