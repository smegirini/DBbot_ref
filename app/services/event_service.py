"""
Event Service
일정 비즈니스 로직 계층
"""
from datetime import date, datetime
from typing import List, Optional
from app.repositories import EventRepository
from app.models.event import (
    EventCreate,
    EventUpdate,
    EventResponse,
    EventListParams,
    EventStatistics
)
from app.models.base import PaginatedResponse
from app.utils import LoggerMixin, EventNotFoundError, ValidationError


class EventService(LoggerMixin):
    """일정 서비스"""

    def __init__(self, event_repo: EventRepository):
        """
        Initialize event service

        Args:
            event_repo: Event repository instance
        """
        self.event_repo = event_repo

    async def create_event(self, event_data: EventCreate) -> EventResponse:
        """
        Create new event

        Args:
            event_data: Event creation data

        Returns:
            EventResponse: Created event

        Raises:
            ValidationError: If validation fails
        """
        try:
            # 과거 날짜 검증 제거 - 과거 일정도 등록 가능하도록 함

            # Prepare data for database
            data = event_data.model_dump()
            data['created_at'] = datetime.now()
            data['updated_at'] = datetime.now()
            data['is_deleted'] = 0

            # Create event
            event_id = await self.event_repo.create(data)

            self.logger.info(
                "event_created",
                event_id=event_id,
                title=event_data.title,
                created_by=event_data.created_by
            )

            # Fetch and return created event
            created_event = await self.event_repo.find_by_id(event_id)
            return EventResponse(**created_event)

        except ValidationError:
            raise
        except Exception as e:
            self.logger.error("event_creation_failed", error=str(e))
            raise

    async def get_event(self, event_id: int) -> EventResponse:
        """
        Get event by ID

        Args:
            event_id: Event ID

        Returns:
            EventResponse: Event data

        Raises:
            EventNotFoundError: If event not found
        """
        event = await self.event_repo.find_by_id(event_id)

        if not event:
            raise EventNotFoundError(f"Event with ID {event_id} not found")

        return EventResponse(**event)

    async def update_event(
        self,
        event_id: int,
        event_data: EventUpdate
    ) -> EventResponse:
        """
        Update event

        Args:
            event_id: Event ID
            event_data: Event update data

        Returns:
            EventResponse: Updated event

        Raises:
            EventNotFoundError: If event not found
        """
        # Check if event exists
        exists = await self.event_repo.exists(event_id)
        if not exists:
            raise EventNotFoundError(f"Event with ID {event_id} not found")

        # Prepare update data (only non-None fields)
        update_data = {k: v for k, v in event_data.model_dump().items() if v is not None}
        update_data['updated_at'] = datetime.now()

        # Update event
        await self.event_repo.update(event_id, update_data)

        self.logger.info("event_updated", event_id=event_id)

        # Return updated event
        return await self.get_event(event_id)

    async def delete_event(self, event_id: int, soft: bool = True) -> bool:
        """
        Delete event

        Args:
            event_id: Event ID
            soft: If True, perform soft delete

        Returns:
            bool: True if deleted

        Raises:
            EventNotFoundError: If event not found
        """
        exists = await self.event_repo.exists(event_id)
        if not exists:
            raise EventNotFoundError(f"Event with ID {event_id} not found")

        result = await self.event_repo.delete(event_id, soft=soft)

        if result:
            self.logger.info(
                "event_deleted",
                event_id=event_id,
                soft_delete=soft
            )

        return result

    async def list_events(
        self,
        params: EventListParams,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResponse:
        """
        List events with filters

        Args:
            params: Event list parameters
            page: Page number
            page_size: Page size

        Returns:
            PaginatedResponse: Paginated event list
        """
        # Build query based on parameters
        if params.start_date and params.end_date:
            events = await self.event_repo.find_by_date_range(
                params.start_date,
                params.end_date,
                params.room_id
            )
        elif params.keyword:
            events = await self.event_repo.search(
                params.keyword,
                params.room_id
            )
        elif params.room_id:
            events = await self.event_repo.find_by_room(params.room_id)
        else:
            events = await self.event_repo.find_upcoming_events(
                limit=page_size,
                room_id=params.room_id
            )

        # Apply pagination
        total = len(events)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_events = events[start:end]

        # Convert to response models
        event_responses = [EventResponse(**event) for event in paginated_events]

        return PaginatedResponse.create(
            items=event_responses,
            total=total,
            page=page,
            page_size=page_size
        )

    async def get_upcoming_events(
        self,
        limit: int = 10,
        room_id: Optional[int] = None
    ) -> List[EventResponse]:
        """
        Get upcoming events

        Args:
            limit: Maximum number of events
            room_id: Optional room ID filter

        Returns:
            List[EventResponse]: List of upcoming events
        """
        events = await self.event_repo.find_upcoming_events(limit, room_id)
        return [EventResponse(**event) for event in events]

    async def get_statistics(
        self,
        room_id: Optional[int] = None
    ) -> EventStatistics:
        """
        Get event statistics

        Args:
            room_id: Optional room ID filter

        Returns:
            EventStatistics: Event statistics
        """
        stats = await self.event_repo.get_statistics(room_id)

        # Get events by month (last 6 months)
        events_by_month = {}
        today = date.today()

        for i in range(6):
            month = today.month - i
            year = today.year

            if month <= 0:
                month += 12
                year -= 1

            count = await self.event_repo.count_by_month(year, month, room_id)
            month_key = f"{year}-{month:02d}"
            events_by_month[month_key] = count

        return EventStatistics(
            total_events=stats['total_events'],
            upcoming_events=stats['upcoming_events'],
            past_events=stats['past_events'],
            events_by_month=events_by_month
        )

    async def get_events_by_date(
        self,
        query_date: date,
        room_id: Optional[int] = None
    ) -> List[EventResponse]:
        """
        Get events for a specific date

        Args:
            query_date: Date to query
            room_id: Optional room ID filter

        Returns:
            List[EventResponse]: List of events on that date
        """
        try:
            events = await self.event_repo.find_by_date(query_date, room_id)

            self.logger.info(
                "events_queried_by_date",
                date=str(query_date),
                count=len(events),
                room_id=room_id
            )

            return [EventResponse(**event) for event in events]

        except Exception as e:
            self.logger.error("get_events_by_date_failed", error=str(e))
            raise

    async def delete_events_by_date(
        self,
        delete_date: date,
        room_id: Optional[int] = None,
        created_by: Optional[str] = None
    ) -> int:
        """
        Delete all events for a specific date

        Args:
            delete_date: Date to delete events from
            room_id: Optional room ID filter
            created_by: Optional creator filter (only delete own events)

        Returns:
            int: Number of events deleted
        """
        try:
            deleted_count = await self.event_repo.delete_by_date(
                delete_date,
                room_id,
                created_by
            )

            self.logger.info(
                "events_deleted_by_date",
                date=str(delete_date),
                count=deleted_count,
                room_id=room_id,
                created_by=created_by
            )

            return deleted_count

        except Exception as e:
            self.logger.error("delete_events_by_date_failed", error=str(e))
            raise

    async def get_events_by_date_range(
        self,
        start_date: date,
        end_date: date,
        room_id: Optional[int] = None
    ) -> List[EventResponse]:
        """
        Get events within a date range

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            room_id: Optional room ID filter

        Returns:
            List[EventResponse]: List of events in date range
        """
        try:
            events = await self.event_repo.find_by_date_range(
                start_date,
                end_date,
                room_id
            )

            self.logger.info(
                "events_queried_by_date_range",
                start_date=str(start_date),
                end_date=str(end_date),
                count=len(events),
                room_id=room_id
            )

            return [EventResponse(**event) for event in events]

        except Exception as e:
            self.logger.error("get_events_by_date_range_failed", error=str(e))
            raise
