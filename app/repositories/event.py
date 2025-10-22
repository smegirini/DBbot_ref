"""
Event Repository
일정 데이터 접근 계층
"""
from datetime import date, datetime
from typing import Optional, List
from app.repositories.base import BaseRepository
from app.models.event import EventInDB, EventListParams


class EventRepository(BaseRepository[EventInDB]):
    """일정 Repository"""

    @property
    def table_name(self) -> str:
        return "events"

    async def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
        room_id: Optional[int] = None
    ) -> List[dict]:
        """
        Find events within date range

        Args:
            start_date: Start date
            end_date: End date
            room_id: Optional room ID filter

        Returns:
            List[dict]: List of events
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE event_date BETWEEN %s AND %s
            AND is_deleted = 0
        """
        params = [start_date, end_date]

        if room_id is not None:
            query += " AND room_id = %s"
            params.append(room_id)

        query += " ORDER BY event_date ASC, event_time ASC"

        return await self.db.fetch_all(query, tuple(params))

    async def find_upcoming_events(
        self,
        limit: int = 10,
        room_id: Optional[int] = None
    ) -> List[dict]:
        """
        Find upcoming events

        Args:
            limit: Maximum number of events
            room_id: Optional room ID filter

        Returns:
            List[dict]: List of upcoming events
        """
        today = date.today()
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE event_date >= %s
            AND is_deleted = 0
        """
        params = [today]

        if room_id is not None:
            query += " AND room_id = %s"
            params.append(room_id)

        query += " ORDER BY event_date ASC, event_time ASC LIMIT %s"
        params.append(limit)

        return await self.db.fetch_all(query, tuple(params))

    async def find_by_room(
        self,
        room_id: int,
        limit: int = 50
    ) -> List[dict]:
        """
        Find events by room ID

        Args:
            room_id: Room ID
            limit: Maximum number of events

        Returns:
            List[dict]: List of events
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE room_id = %s
            AND is_deleted = 0
            ORDER BY event_date DESC, event_time DESC
            LIMIT %s
        """
        return await self.db.fetch_all(query, (room_id, limit))

    async def search(
        self,
        keyword: str,
        room_id: Optional[int] = None
    ) -> List[dict]:
        """
        Search events by keyword

        Args:
            keyword: Search keyword
            room_id: Optional room ID filter

        Returns:
            List[dict]: List of matching events
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE (title LIKE %s OR description LIKE %s)
            AND is_deleted = 0
        """
        search_term = f"%{keyword}%"
        params = [search_term, search_term]

        if room_id is not None:
            query += " AND room_id = %s"
            params.append(room_id)

        query += " ORDER BY event_date DESC"

        return await self.db.fetch_all(query, tuple(params))

    async def count_by_month(
        self,
        year: int,
        month: int,
        room_id: Optional[int] = None
    ) -> int:
        """
        Count events in a specific month

        Args:
            year: Year
            month: Month
            room_id: Optional room ID filter

        Returns:
            int: Event count
        """
        query = f"""
            SELECT COUNT(*) as count FROM {self.table_name}
            WHERE YEAR(event_date) = %s
            AND MONTH(event_date) = %s
            AND is_deleted = 0
        """
        params = [year, month]

        if room_id is not None:
            query += " AND room_id = %s"
            params.append(room_id)

        result = await self.db.fetch_one(query, tuple(params))
        return result['count'] if result else 0

    async def get_statistics(
        self,
        room_id: Optional[int] = None
    ) -> dict:
        """
        Get event statistics

        Args:
            room_id: Optional room ID filter

        Returns:
            dict: Statistics data
        """
        today = date.today()
        base_query = f"SELECT COUNT(*) as count FROM {self.table_name} WHERE is_deleted = 0"
        room_filter = " AND room_id = %s" if room_id else ""

        # Total events
        total_query = base_query + room_filter
        total_params = (room_id,) if room_id else ()
        total_result = await self.db.fetch_one(total_query, total_params)
        total_events = total_result['count'] if total_result else 0

        # Upcoming events
        upcoming_query = base_query + " AND event_date >= %s" + room_filter
        upcoming_params = (today, room_id) if room_id else (today,)
        upcoming_result = await self.db.fetch_one(upcoming_query, upcoming_params)
        upcoming_events = upcoming_result['count'] if upcoming_result else 0

        # Past events
        past_query = base_query + " AND event_date < %s" + room_filter
        past_params = (today, room_id) if room_id else (today,)
        past_result = await self.db.fetch_one(past_query, past_params)
        past_events = past_result['count'] if past_result else 0

        return {
            'total_events': total_events,
            'upcoming_events': upcoming_events,
            'past_events': past_events
        }

    async def find_by_date(
        self,
        query_date: date,
        room_id: Optional[int] = None
    ) -> List[dict]:
        """
        Find events for a specific date

        Args:
            query_date: Date to query
            room_id: Optional room ID filter

        Returns:
            List[dict]: List of events on that date
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE event_date = %s
            AND is_deleted = 0
        """
        params = [query_date]

        if room_id is not None:
            query += " AND room_id = %s"
            params.append(room_id)

        query += " ORDER BY event_time ASC"

        return await self.db.fetch_all(query, tuple(params))

    async def delete_by_date(
        self,
        delete_date: date,
        room_id: Optional[int] = None,
        created_by: Optional[str] = None
    ) -> int:
        """
        Delete events for a specific date (soft delete)

        Args:
            delete_date: Date to delete events from
            room_id: Optional room ID filter
            created_by: Optional creator filter

        Returns:
            int: Number of events deleted
        """
        query = f"""
            UPDATE {self.table_name}
            SET is_deleted = 1, updated_at = %s
            WHERE event_date = %s
            AND is_deleted = 0
        """
        params = [datetime.now(), delete_date]

        if room_id is not None:
            query += " AND room_id = %s"
            params.append(room_id)

        if created_by is not None:
            query += " AND created_by = %s"
            params.append(created_by)

        result = await self.db.execute(query, tuple(params))
        return result  # Returns number of rows affected
