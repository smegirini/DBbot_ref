"""
Notification Service
알림 및 금요일 일정 브로드캐스트 서비스
"""
from datetime import datetime, date, timedelta
from typing import Optional, List
import asyncio

from app.config import settings
from app.services import EventService
from app.utils import LoggerMixin, ExternalServiceError


class NotificationService(LoggerMixin):
    """
    알림 전송 서비스

    - '알림' 키워드: 도우미방에서 수신 시 오늘 일정을 다른 방들에 브로드캐스트
    - '금요일' 키워드: 도우미방에서 금요일에 수신 시 차주 일정을 다른 방들에 브로드캐스트
    """

    def __init__(self, event_service: EventService):
        """
        Initialize Notification Service

        Args:
            event_service: Event service instance
        """
        self.event_service = event_service

    async def send_today_schedule_notification(self, chat) -> Optional[str]:
        """
        오늘 일정 알림 전송 (ChatContext 기반)

        도우미방에서 '알림' 메시지 수신 시:
        1. 주말인지 확인 (주말이면 전송 안함)
        2. 오늘 일정 조회
        3. 설정된 알림방들에 브로드캐스트 (chat.reply(message, room_id=target) 사용)

        Args:
            chat: ChatContext 객체 (api 속성으로 IrisAPI 접근 가능)

        Returns:
            Optional[str]: 응답 메시지 (도우미방에만 전송)
        """
        try:
            # 도우미방 확인
            room_name = chat.room.name
            if room_name != settings.notification.helper_room_name:
                self.logger.info(
                    "notification_ignored_not_helper_room",
                    room_name=room_name,
                    expected=settings.notification.helper_room_name
                )
                return None

            # 주말 체크
            today = date.today()
            weekday = today.weekday()  # 월요일=0, 일요일=6

            if weekday in [5, 6]:  # 토요일, 일요일
                self.logger.info("notification_skipped_weekend", day=weekday)
                return "⚠️ 주말에는 알림을 전송하지 않습니다."

            # 알림 대상 방 목록 가져오기
            target_rooms = settings.notification.get_notification_rooms_list()

            if not target_rooms:
                self.logger.warning("no_notification_rooms_configured")
                return "⚠️ 알림을 전송할 방이 설정되지 않았습니다."

            # 각 방별로 오늘 일정 조회 및 전송
            sent_count = 0
            failed_rooms = []

            for target_room_name in target_rooms:
                try:
                    # PyKV 영구 저장소에서 방 이름 → room_id 찾기
                    from app.utils import room_storage

                    target_room_id = room_storage.get_room_id(target_room_name)

                    if not target_room_id:
                        self.logger.warning(
                            "target_room_not_found",
                            room_name=target_room_name,
                            message=f"'{target_room_name}' 방을 찾을 수 없습니다. 해당 방에서 메시지를 보내면 자동 등록됩니다."
                        )
                        failed_rooms.append(target_room_name)
                        continue

                    # 해당 방의 오늘 일정 조회
                    events = await self.event_service.get_events_by_date(today, target_room_id)

                    # 일정이 없으면 전송 안함
                    if not events:
                        self.logger.info(
                            "no_events_for_notification",
                            room_name=target_room_name,
                            date=today
                        )
                        continue

                    # 메시지 구성 (ref_file 양식)
                    message = f"📅 {today.strftime('%Y년 %m월 %d일')} 일정\n\n"
                    schedules = [f"- {event.created_by}: {event.title}" for event in events]
                    message += "\n".join(schedules)

                    # 메시지 전송 (ChatContext.reply 사용 - room_id 파라미터로 다른 방에 전송)
                    chat.reply(message, room_id=target_room_id)
                    sent_count += 1

                    self.logger.info(
                        "notification_sent",
                        target_room=target_room_name,
                        event_count=len(events)
                    )

                    # 방별 전송 딜레이 (0.5초)
                    await asyncio.sleep(0.5)

                except Exception as e:
                    self.logger.error(
                        "notification_send_failed",
                        target_room=target_room_name,
                        error=str(e)
                    )
                    failed_rooms.append(target_room_name)

            # 결과 메시지 (도우미방에만 표시)
            result_msg = f"✅ {sent_count}개 방에 오늘 일정 알림을 전송했습니다."

            if failed_rooms:
                result_msg += f"\n❌ 실패: {', '.join(failed_rooms)}"

            return result_msg

        except Exception as e:
            self.logger.error("today_schedule_notification_failed", error=str(e))
            raise ExternalServiceError(f"오늘 일정 알림 전송 실패: {str(e)}")

    async def send_next_week_schedule_notification(self, chat) -> Optional[str]:
        """
        차주 일정 알림 전송 (ChatContext 기반)

        도우미방에서 '금요일' 메시지 수신 시:
        1. 금요일인지 확인 (금요일 아니면 전송 안함)
        2. 차주(월~금) 일정 조회
        3. 설정된 알림방들에 브로드캐스트 (chat.reply(message, room_id=target) 사용)

        Args:
            chat: ChatContext 객체

        Returns:
            Optional[str]: 응답 메시지 (도우미방에만 전송)
        """
        try:
            # 도우미방 확인
            room_name = chat.room.name
            if room_name != settings.notification.helper_room_name:
                self.logger.info(
                    "next_week_notification_ignored_not_helper_room",
                    room_name=room_name,
                    expected=settings.notification.helper_room_name
                )
                return None

            # 금요일 체크
            today = date.today()
            weekday = today.weekday()  # 금요일=4

            if weekday != 4:
                self.logger.info("next_week_notification_not_friday", day=weekday)
                return "⚠️ 차주 일정 알림은 금요일에만 전송됩니다."

            # 알림 대상 방 목록 가져오기
            target_rooms = settings.notification.get_notification_rooms_list()

            if not target_rooms:
                self.logger.warning("no_notification_rooms_configured")
                return "⚠️ 알림을 전송할 방이 설정되지 않았습니다."

            # 차주 월요일부터 금요일까지 날짜 계산
            days_until_next_monday = 7 - weekday  # 금요일 기준 다음 월요일까지 일수 = 3
            next_monday = today + timedelta(days=days_until_next_monday)
            next_friday = next_monday + timedelta(days=4)

            # 각 방별로 차주 일정 조회 및 전송
            sent_count = 0
            failed_rooms = []

            for target_room_name in target_rooms:
                try:
                    # PyKV 영구 저장소에서 방 이름 → room_id 찾기
                    from app.utils import room_storage

                    target_room_id = room_storage.get_room_id(target_room_name)

                    if not target_room_id:
                        self.logger.warning(
                            "target_room_not_found",
                            room_name=target_room_name,
                            message=f"'{target_room_name}' 방을 찾을 수 없습니다. 해당 방에서 메시지를 보내면 자동 등록됩니다."
                        )
                        failed_rooms.append(target_room_name)
                        continue

                    # 해당 방의 차주(월~금) 일정 조회
                    events = await self.event_service.get_events_by_date_range(
                        next_monday,
                        next_friday,
                        target_room_id
                    )

                    # 일정이 없으면 전송 안함
                    if not events:
                        self.logger.info(
                            "no_next_week_events_for_notification",
                            room_name=target_room_name,
                            date_range=f"{next_monday} ~ {next_friday}"
                        )
                        continue

                    # 메시지 구성 (ref_file 양식: 날짜별로 그룹화)
                    message = f"📅 차주 일정 ({next_monday.strftime('%m/%d')} ~ {next_friday.strftime('%m/%d')})\n\n"

                    # 날짜별로 그룹화
                    events_by_date = {}
                    for event in events:
                        event_date = event.event_date
                        if event_date not in events_by_date:
                            events_by_date[event_date] = []
                        events_by_date[event_date].append(event)

                    # 날짜순으로 정렬하여 출력
                    for event_date in sorted(events_by_date.keys()):
                        # 요일 이름 가져오기
                        weekday_names = ['월', '화', '수', '목', '금', '토', '일']
                        weekday_name = weekday_names[event_date.weekday()]

                        message += f"[{event_date.strftime('%m/%d')} ({weekday_name})]\n"

                        for event in events_by_date[event_date]:
                            message += f"- {event.created_by}: {event.title}\n"

                        message += "\n"

                    # 메시지 전송 (ChatContext.reply 사용 - room_id 파라미터로 다른 방에 전송)
                    chat.reply(message.strip(), room_id=target_room_id)
                    sent_count += 1

                    self.logger.info(
                        "next_week_notification_sent",
                        target_room=target_room_name,
                        event_count=len(events)
                    )

                    # 방별 전송 딜레이 (0.5초)
                    await asyncio.sleep(0.5)

                except Exception as e:
                    self.logger.error(
                        "next_week_notification_send_failed",
                        target_room=target_room_name,
                        error=str(e)
                    )
                    failed_rooms.append(target_room_name)

            # 결과 메시지 (도우미방에만 표시)
            result_msg = f"✅ {sent_count}개 방에 차주 일정 알림을 전송했습니다."

            if failed_rooms:
                result_msg += f"\n❌ 실패: {', '.join(failed_rooms)}"

            return result_msg

        except Exception as e:
            self.logger.error("next_week_schedule_notification_failed", error=str(e))
            raise ExternalServiceError(f"차주 일정 알림 전송 실패: {str(e)}")
