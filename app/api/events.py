"""
Events API
일정 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional

from app.services import EventService
from app.repositories import EventRepository
from app.models.event import (
    EventCreate,
    EventUpdate,
    EventResponse,
    EventListParams,
    EventStatistics
)
from app.models.base import BaseResponse, PaginatedResponse
from app.utils import get_db, DatabaseManager, EventNotFoundError, ValidationError

router = APIRouter(prefix="/events", tags=["Events"])


def get_event_service(
    db: DatabaseManager = Depends(get_db)
) -> EventService:
    """
    Dependency to get event service

    Args:
        db: Database manager

    Returns:
        EventService: Event service instance
    """
    event_repo = EventRepository(db)
    return EventService(event_repo)


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    service: EventService = Depends(get_event_service)
) -> EventResponse:
    """
    Create new event

    Args:
        event_data: Event creation data
        service: Event service

    Returns:
        EventResponse: Created event
    """
    try:
        return await service.create_event(event_data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create event: {str(e)}"
        )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    service: EventService = Depends(get_event_service)
) -> EventResponse:
    """
    Get event by ID

    Args:
        event_id: Event ID
        service: Event service

    Returns:
        EventResponse: Event data
    """
    try:
        return await service.get_event(event_id)
    except EventNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    event_data: EventUpdate,
    service: EventService = Depends(get_event_service)
) -> EventResponse:
    """
    Update event

    Args:
        event_id: Event ID
        event_data: Event update data
        service: Event service

    Returns:
        EventResponse: Updated event
    """
    try:
        return await service.update_event(event_id, event_data)
    except EventNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update event: {str(e)}"
        )


@router.delete("/{event_id}", response_model=BaseResponse)
async def delete_event(
    event_id: int,
    soft: bool = Query(default=True, description="Soft delete if True"),
    service: EventService = Depends(get_event_service)
) -> BaseResponse:
    """
    Delete event

    Args:
        event_id: Event ID
        soft: Soft delete flag
        service: Event service

    Returns:
        BaseResponse: Delete result
    """
    try:
        result = await service.delete_event(event_id, soft=soft)
        return BaseResponse(
            success=result,
            message=f"Event {event_id} deleted successfully"
        )
    except EventNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("", response_model=PaginatedResponse)
async def list_events(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    room_id: Optional[int] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: EventService = Depends(get_event_service)
) -> PaginatedResponse:
    """
    List events with filters

    Args:
        start_date: Start date filter (YYYY-MM-DD)
        end_date: End date filter (YYYY-MM-DD)
        room_id: Room ID filter
        keyword: Search keyword
        page: Page number
        page_size: Page size
        service: Event service

    Returns:
        PaginatedResponse: Paginated event list
    """
    from datetime import date as dt_date

    # Parse dates
    parsed_start = dt_date.fromisoformat(start_date) if start_date else None
    parsed_end = dt_date.fromisoformat(end_date) if end_date else None

    params = EventListParams(
        start_date=parsed_start,
        end_date=parsed_end,
        room_id=room_id,
        keyword=keyword
    )

    return await service.list_events(params, page, page_size)


@router.get("/upcoming/list", response_model=List[EventResponse])
async def get_upcoming_events(
    limit: int = Query(default=10, ge=1, le=100),
    room_id: Optional[int] = Query(default=None),
    service: EventService = Depends(get_event_service)
) -> List[EventResponse]:
    """
    Get upcoming events

    Args:
        limit: Maximum number of events
        room_id: Optional room ID filter
        service: Event service

    Returns:
        List[EventResponse]: List of upcoming events
    """
    return await service.get_upcoming_events(limit, room_id)


@router.get("/statistics/summary", response_model=EventStatistics)
async def get_event_statistics(
    room_id: Optional[int] = Query(default=None),
    service: EventService = Depends(get_event_service)
) -> EventStatistics:
    """
    Get event statistics

    Args:
        room_id: Optional room ID filter
        service: Event service

    Returns:
        EventStatistics: Event statistics
    """
    return await service.get_statistics(room_id)
