"""
Command Service
카카오톡 명령어 파싱 및 라우팅
"""
from typing import Optional
from datetime import datetime, date, timedelta
import re

from app.services import EventService, AIService
from app.services.youtube_service import YouTubeService
from app.services.notification_service import NotificationService
from app.services.pdf_service import PDFService
from app.services.tts_service import TTSService
from app.services.image_service import ImageService
from app.services.crypto_service import CryptoService
from app.services.stock_service import StockService
from app.services.rag_service import RAGService
from app.services.multi_llm_service import MultiLLMService
from app.services.crypto_advanced_service import CryptoAdvancedService
from app.services.playwright_crawler_service import PlaywrightCrawlerService
from app.models.event import EventCreate
from app.utils import LoggerMixin, ValidationError


class CommandService(LoggerMixin):
    """
    명령어 처리 서비스

    카카오톡 메시지에서 명령어를 파싱하고
    적절한 서비스로 라우팅합니다.
    """

    def __init__(
        self,
        event_service: EventService,
        youtube_service: YouTubeService,
        ai_service: AIService,
        notification_service: Optional[NotificationService] = None,
        pdf_service: Optional[PDFService] = None,
        tts_service: Optional[TTSService] = None,
        image_service: Optional[ImageService] = None,
        crypto_service: Optional[CryptoService] = None,
        stock_service: Optional[StockService] = None,
        rag_service: Optional[RAGService] = None,
        multi_llm_service: Optional[MultiLLMService] = None,
        crypto_advanced_service: Optional[CryptoAdvancedService] = None,
        playwright_service: Optional[PlaywrightCrawlerService] = None
    ):
        """
        Initialize Command Service

        Args:
            event_service: Event service instance
            youtube_service: YouTube service instance
            ai_service: AI service instance
            notification_service: Notification service instance (optional)
            pdf_service: PDF service instance (optional)
            tts_service: TTS service instance (optional)
            image_service: Image generation service instance (optional)
            crypto_service: Cryptocurrency service instance (optional)
            stock_service: Stock service instance (optional)
            rag_service: RAG service instance (optional)
            multi_llm_service: Multi-LLM service instance (optional)
            crypto_advanced_service: Advanced crypto analysis service instance (optional)
            playwright_service: Playwright crawler service instance (optional)
        """
        self.event_service = event_service
        self.youtube_service = youtube_service
        self.ai_service = ai_service
        self.notification_service = notification_service
        self.pdf_service = pdf_service
        self.tts_service = tts_service
        self.image_service = image_service
        self.crypto_service = crypto_service
        self.stock_service = stock_service
        self.rag_service = rag_service
        self.multi_llm_service = multi_llm_service
        self.crypto_advanced_service = crypto_advanced_service
        self.playwright_service = playwright_service

    async def process_command(self, chat) -> Optional[str]:
        """
        명령어 처리 (ChatContext 기반)

        Args:
            chat: ChatContext 객체 (room, sender, message, api 포함)

        Returns:
            Optional[str]: 응답 메시지
        """
        try:
            # ChatContext에서 필요한 정보 추출
            command = chat.message.command
            param = chat.message.param
            room_name = chat.room.name
            room_id = chat.room.id
            sender_name = chat.sender.name
            sender_id = chat.sender.id
            full_message = chat.message.msg

            # URL 감지 (유튜브 또는 웹페이지) - 첫 번째 우선순위
            if full_message.startswith('http'):
                return await self._handle_url_message(full_message, room_name, sender_name)

            # 특수 키워드 처리 (ref_file 154~158 라인 호환)
            # '알림' - 오늘 일정을 다른 방에 브로드캐스트
            if full_message.strip() == '알림':
                if self.notification_service:
                    return await self.notification_service.send_today_schedule_notification(chat)
                else:
                    self.logger.warning("notification_service_not_initialized")
                    return None

            # '금요일' - 차주 일정을 다른 방에 브로드캐스트
            if full_message.strip() == '금요일':
                if self.notification_service:
                    return await self.notification_service.send_next_week_schedule_notification(chat)
                else:
                    self.logger.warning("notification_service_not_initialized")
                    return None

            # 명령어 매칭
            match command:
                # 일정 등록 (ref_file 호환: "등록 YYMMDD 내용")
                case "등록":
                    return await self._handle_event_register(param, room_name, room_id, sender_name)

                # 일정 조회 (ref_file 호환: "일정 YYMMDD")
                case "일정":
                    return await self._handle_event_query(param, room_id, sender_name)

                # 일정 삭제 (ref_file 호환: "삭제 YYMMDD")
                case "삭제":
                    return await self._handle_event_delete_by_date(param, room_id, sender_name)

                # 금주일정
                case "금주일정":
                    return await self._handle_this_week_events(room_id)

                # 차주일정
                case "차주일정":
                    return await self._handle_next_week_events(room_id)

                # 신규 스타일 명령어들
                case "일정등록" | "일정추가" | "!일정" | "!event":
                    return await self._handle_event_create(param, room_name, room_id, sender_name)

                case "일정조회" | "일정목록" | "!일정목록" | "!events":
                    return await self._handle_event_list(room_id)

                case "일정삭제" | "!일정삭제":
                    return await self._handle_event_delete(param)

                # 도움말
                case "도움말" | "!help" | "!도움말":
                    return self._get_help_message()

                # AI 대화
                case "!ai" | "!ask":
                    if param:
                        return await self._handle_ai_query(param)
                    return "❓ 질문을 입력해주세요.\n예: !ai 오늘 날씨 어때?"

                # 통계
                case "일정통계" | "!stats":
                    return await self._handle_event_stats(room_id)

                # 이미지 생성
                case "!gi" | "!이미지생성":
                    if param and self.image_service:
                        return await self._handle_image_generation(chat, param)
                    return "💡 사용법: !gi 고양이 그림"

                # 이미지 분석
                case "!분석":
                    if self.image_service:
                        return await self._handle_image_analysis(chat)
                    return "❌ 이미지 분석 서비스를 사용할 수 없습니다."

                # 코인 정보
                case "!코인":
                    if self.crypto_service:
                        if param:
                            return await self._handle_coin_price(param, str(sender_id))
                        else:
                            return "💡 사용법: !코인 BTC 또는 !코인 (전체 시세)"
                    return "❌ 암호화폐 서비스를 사용할 수 없습니다."

                case "!내코인":
                    if self.crypto_service:
                        return await self._handle_my_coins(str(sender_id))
                    return "❌ 암호화폐 서비스를 사용할 수 없습니다."

                case "!김프":
                    if self.crypto_service:
                        return await self._handle_kimchi_premium()
                    return "❌ 암호화폐 서비스를 사용할 수 없습니다."

                case "!코인등록":
                    if self.crypto_service and param:
                        return await self._handle_coin_add(str(sender_id), param)
                    return "💡 사용법: !코인등록 BTC 1.5 50000000"

                case "!코인삭제":
                    if self.crypto_service and param:
                        return await self._handle_coin_remove(str(sender_id), param)
                    return "💡 사용법: !코인삭제 BTC"

                # 주식 차트
                case "!주식":
                    if self.stock_service and param:
                        return await self._handle_stock_chart(chat, param)
                    return "💡 사용법: !주식 삼성전자"

                # TTS
                case "!tts":
                    if self.tts_service and param:
                        return await self._handle_tts(chat, param)
                    return "💡 사용법: !tts 안녕하세요"

                # RAG 검색
                case "!rag" | "!검색":
                    if self.rag_service and param:
                        return await self._handle_rag_query(param)
                    return "💡 사용법: !rag 최신 AI 트렌드"

                # Multi-LLM 질문
                case "!llm" | "!gpt":
                    if self.multi_llm_service and param:
                        return await self._handle_multi_llm_query(param)
                    return "💡 사용법: !llm 파이썬으로 피보나치 수열 생성하는 법"

                # 고급 코인 분석
                case "!코인분석":
                    if self.crypto_advanced_service and param:
                        return await self._handle_crypto_analysis(param)
                    return "💡 사용법: !코인분석 bitcoin"

                # 웹페이지 크롤링
                case "!크롤":
                    if self.playwright_service and param:
                        return await self._handle_web_crawl(param)
                    return "💡 사용법: !크롤 https://example.com"

                # 기본 응답 없음 (일반 대화는 처리하지 않음)
                case _:
                    return None

        except Exception as e:
            self.logger.error(
                "command_processing_failed",
                command=command,
                error=str(e)
            )
            return f"❌ 명령어 처리 중 오류가 발생했습니다: {str(e)}"

    def _contains_url(self, text: str) -> bool:
        """
        텍스트에 URL이 포함되어 있는지 확인

        Args:
            text: 검사할 텍스트

        Returns:
            bool: URL 포함 여부
        """
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return bool(re.search(url_pattern, text))

    async def _handle_url_message(self, message: str, room_name: str, sender_name: str) -> str:
        """
        URL 포함 메시지 처리 (유튜브/웹페이지 요약)

        Args:
            message: 메시지 텍스트
            room_name: 방 이름
            sender_name: 발신자 이름

        Returns:
            str: 요약 결과
        """
        try:
            # URL 추출
            url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            urls = re.findall(url_pattern, message)

            if not urls:
                return None

            url = urls[0]  # 첫 번째 URL 처리

            self.logger.info("url_detected", url=url, sender=sender_name)

            # 유튜브 URL 체크
            if 'youtube.com' in url or 'youtu.be' in url:
                summary = await self.youtube_service.summarize_video(url)
                return f"📺 유튜브 영상 요약\n\n{summary}"
            # 네이버 블로그
            elif 'blog.naver.com' in url:
                summary = await self.youtube_service.summarize_webpage(url)
                return f"📝 블로그 요약\n\n{summary}"
            # Medium
            elif 'medium.com' in url:
                summary = await self.youtube_service.summarize_webpage(url)
                return f"📰 Medium 요약\n\n{summary}"
            else:
                # 일반 웹페이지 요약
                summary = await self.youtube_service.summarize_webpage(url)
                return f"🌐 웹페이지 요약\n\n{summary}"

        except Exception as e:
            self.logger.error("url_handling_failed", error=str(e))
            return f"❌ URL 처리 실패: {str(e)}"

    async def _handle_event_register(
        self,
        param: str,
        room_name: str,
        room_id: int,
        sender_name: str
    ) -> str:
        """
        일정 등록 처리 (ref_file 호환)
        형식: 등록 250121 내용

        Args:
            param: 일정 정보 (YYMMDD 내용)
            room_name: 방 이름
            room_id: 방 ID
            sender_name: 발신자 이름

        Returns:
            str: 응답 메시지
        """
        try:
            if not param:
                return (
                    "📅 일정 등록 형식:\n"
                    "등록 250121 팀 회의\n"
                    "또는\n"
                    "등록 25-01-21 팀 회의"
                )

            # 파라미터 파싱
            parts = param.split(maxsplit=1)

            if len(parts) < 2:
                return "❌ 형식이 올바르지 않습니다.\n예: 등록 250121 팀 회의"

            date_str = parts[0]
            title = parts[1]

            # 6자리 날짜 파싱 (YYMMDD)
            event_date = self._parse_short_date(date_str)

            # 일정 생성
            event_data = EventCreate(
                title=title,
                event_date=event_date,
                event_time=None,  # 시간 없음
                room_id=room_id,
                created_by=sender_name
            )

            created_event = await self.event_service.create_event(event_data)

            # 성공 메시지 (ref_file 양식)
            return (
                f"✅ {sender_name}님의 일정이 등록되었습니다.\n"
                f"📅 날짜: {created_event.event_date}\n"
                f"📝 내용: {created_event.title}"
            )

        except ValidationError as e:
            return f"❌ 입력 오류: {str(e)}"
        except Exception as e:
            self.logger.error("event_register_failed", error=str(e))
            return f"❌ 일정 등록 실패: {str(e)}"

    async def _handle_event_query(
        self,
        param: str,
        room_id: int,
        sender_name: str
    ) -> str:
        """
        특정 날짜 일정 조회 (ref_file 호환)
        형식: 일정 250121

        Args:
            param: 날짜 (YYMMDD)
            room_id: 방 ID
            sender_name: 발신자 이름

        Returns:
            str: 일정 정보
        """
        try:
            if not param:
                # 파라미터 없으면 다가오는 일정 조회
                return await self._handle_event_list(room_id)

            # 날짜 파싱
            date_str = param.strip()
            query_date = self._parse_short_date(date_str)

            # 해당 날짜의 일정 조회
            events = await self.event_service.get_events_by_date(query_date, room_id)

            if not events:
                return f"📅 {query_date}에 등록된 일정이 없습니다."

            # ref_file 양식: "- 작성자: 내용"
            message = f"📅 {query_date} 일정\n\n"
            schedules = [f"- {event.created_by}: {event.title}" for event in events]
            message += "\n".join(schedules)

            return message

        except Exception as e:
            self.logger.error("event_query_failed", error=str(e))
            return f"❌ 일정 조회 실패: {str(e)}"

    async def _handle_event_delete_by_date(
        self,
        param: str,
        room_id: int,
        sender_name: str
    ) -> str:
        """
        특정 날짜 일정 삭제 (ref_file 호환)
        형식: 삭제 250121

        Args:
            param: 날짜 (YYMMDD)
            room_id: 방 ID
            sender_name: 발신자 이름

        Returns:
            str: 응답 메시지
        """
        try:
            if not param:
                return "❌ 날짜를 입력해주세요.\n예: 삭제 250121"

            # 날짜 파싱
            date_str = param.strip()
            delete_date = self._parse_short_date(date_str)

            # 해당 날짜의 본인 일정 삭제
            deleted_count = await self.event_service.delete_events_by_date(
                delete_date,
                room_id,
                sender_name
            )

            if deleted_count == 0:
                return f"❌ {delete_date}에 등록된 일정이 없습니다."

            return f"✅ {sender_name}님의 {delete_date} 일정이 삭제되었습니다."

        except Exception as e:
            self.logger.error("event_delete_by_date_failed", error=str(e))
            return f"❌ 일정 삭제 실패: {str(e)}"

    async def _handle_this_week_events(self, room_id: int) -> str:
        """
        금주일정 조회

        Args:
            room_id: 방 ID

        Returns:
            str: 금주 일정
        """
        try:
            today = date.today()
            # 이번 주 월요일
            monday = today - timedelta(days=today.weekday())
            # 이번 주 일요일
            sunday = monday + timedelta(days=6)

            events = await self.event_service.get_events_by_date_range(
                start_date=monday,
                end_date=sunday,
                room_id=room_id
            )

            if not events:
                return f"📅 금주({monday} ~ {sunday})에 등록된 일정이 없습니다."

            message = f"📅 금주 일정 ({monday} ~ {sunday})\n\n"

            current_date = None
            for event in events:
                if current_date != event.event_date:
                    current_date = event.event_date
                    weekday = ['월', '화', '수', '목', '금', '토', '일'][current_date.weekday()]
                    message += f"\n▪️ {current_date} ({weekday})\n"

                time_str = event.event_time.strftime("%H:%M") if event.event_time else "시간 미정"
                message += f"  • {time_str} - {event.title} (등록: {event.created_by})\n"

            return message.strip()

        except Exception as e:
            self.logger.error("this_week_events_failed", error=str(e))
            return f"❌ 금주일정 조회 실패: {str(e)}"

    async def _handle_next_week_events(self, room_id: int) -> str:
        """
        차주일정 조회

        Args:
            room_id: 방 ID

        Returns:
            str: 차주 일정
        """
        try:
            today = date.today()
            # 다음 주 월요일
            next_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=1)
            # 다음 주 일요일
            next_sunday = next_monday + timedelta(days=6)

            events = await self.event_service.get_events_by_date_range(
                start_date=next_monday,
                end_date=next_sunday,
                room_id=room_id
            )

            if not events:
                return f"📅 차주({next_monday} ~ {next_sunday})에 등록된 일정이 없습니다."

            message = f"📅 차주 일정 ({next_monday} ~ {next_sunday})\n\n"

            current_date = None
            for event in events:
                if current_date != event.event_date:
                    current_date = event.event_date
                    weekday = ['월', '화', '수', '목', '금', '토', '일'][current_date.weekday()]
                    message += f"\n▪️ {current_date} ({weekday})\n"

                time_str = event.event_time.strftime("%H:%M") if event.event_time else "시간 미정"
                message += f"  • {time_str} - {event.title} (등록: {event.created_by})\n"

            return message.strip()

        except Exception as e:
            self.logger.error("next_week_events_failed", error=str(e))
            return f"❌ 차주일정 조회 실패: {str(e)}"

    async def _handle_event_create(
        self,
        param: str,
        room_name: str,
        room_id: int,
        sender_name: str
    ) -> str:
        """
        일정 등록 처리 (신규 스타일)

        Args:
            param: 일정 정보 (날짜 시간 제목)
            room_name: 방 이름
            room_id: 방 ID
            sender_name: 발신자 이름

        Returns:
            str: 응답 메시지
        """
        try:
            if not param:
                return (
                    "📅 일정 등록 형식:\n"
                    "일정등록 2025-10-25 14:00 팀 회의\n"
                    "또는\n"
                    "일정등록 2025-10-25 팀 회의 (시간 생략 가능)"
                )

            # 파라미터 파싱
            parts = param.split(maxsplit=2)

            if len(parts) < 2:
                return "❌ 형식이 올바르지 않습니다. 최소 날짜와 제목이 필요합니다."

            # 날짜 파싱
            event_date_str = parts[0]
            event_date = self._parse_date(event_date_str)

            # 시간과 제목 분리
            if len(parts) == 3:
                # 시간이 있는지 확인
                time_or_title = parts[1]
                if ':' in time_or_title:
                    # 시간 형식
                    event_time = self._parse_time(time_or_title)
                    title = parts[2]
                else:
                    # 시간 없음
                    event_time = None
                    title = ' '.join(parts[1:])
            else:
                event_time = None
                title = parts[1]

            # 일정 생성
            event_data = EventCreate(
                title=title,
                event_date=event_date,
                event_time=event_time,
                room_id=room_id,
                created_by=sender_name
            )

            created_event = await self.event_service.create_event(event_data)

            # 성공 메시지
            time_str = created_event.event_time.strftime("%H:%M") if created_event.event_time else "시간 미정"
            return (
                f"✅ 일정이 등록되었습니다!\n\n"
                f"📅 날짜: {created_event.event_date}\n"
                f"🕐 시간: {time_str}\n"
                f"📝 제목: {created_event.title}\n"
                f"👤 등록자: {created_event.created_by}"
            )

        except ValidationError as e:
            return f"❌ 입력 오류: {str(e)}"
        except Exception as e:
            self.logger.error("event_create_failed", error=str(e))
            return f"❌ 일정 등록 실패: {str(e)}"

    async def _handle_event_list(self, room_id: int) -> str:
        """
        일정 목록 조회

        Args:
            room_id: 방 ID

        Returns:
            str: 일정 목록
        """
        try:
            events = await self.event_service.get_upcoming_events(
                limit=10,
                room_id=room_id
            )

            if not events:
                return "📅 예정된 일정이 없습니다."

            message = "📅 다가오는 일정 (최대 10개)\n\n"

            for i, event in enumerate(events, 1):
                time_str = event.event_time.strftime("%H:%M") if event.event_time else "시간 미정"
                message += (
                    f"{i}. [{event.event_date}] {time_str}\n"
                    f"   {event.title}\n"
                    f"   등록: {event.created_by}\n\n"
                )

            return message.strip()

        except Exception as e:
            self.logger.error("event_list_failed", error=str(e))
            return f"❌ 일정 조회 실패: {str(e)}"

    async def _handle_event_delete(self, param: str) -> str:
        """
        일정 삭제 (ID 기반)

        Args:
            param: 일정 ID

        Returns:
            str: 응답 메시지
        """
        try:
            if not param or not param.isdigit():
                return "❌ 일정 ID를 입력해주세요.\n예: 일정삭제 123"

            event_id = int(param)
            result = await self.event_service.delete_event(event_id)

            if result:
                return f"✅ 일정 #{event_id}이 삭제되었습니다."
            else:
                return f"❌ 일정 #{event_id}을 찾을 수 없습니다."

        except Exception as e:
            self.logger.error("event_delete_failed", error=str(e))
            return f"❌ 일정 삭제 실패: {str(e)}"

    async def _handle_event_stats(self, room_id: int) -> str:
        """
        일정 통계 조회

        Args:
            room_id: 방 ID

        Returns:
            str: 통계 정보
        """
        try:
            stats = await self.event_service.get_statistics(room_id)

            message = (
                f"📊 일정 통계\n\n"
                f"전체 일정: {stats.total_events}개\n"
                f"다가오는 일정: {stats.upcoming_events}개\n"
                f"지난 일정: {stats.past_events}개\n"
            )

            return message

        except Exception as e:
            self.logger.error("event_stats_failed", error=str(e))
            return f"❌ 통계 조회 실패: {str(e)}"

    async def _handle_ai_query(self, query: str) -> str:
        """
        AI 질의 처리

        Args:
            query: 질문

        Returns:
            str: AI 응답
        """
        try:
            response = await self.ai_service.generate_text(query)
            return f"🤖 AI 응답:\n\n{response}"

        except Exception as e:
            self.logger.error("ai_query_failed", error=str(e))
            return f"❌ AI 응답 실패: {str(e)}"

    def _get_help_message(self) -> str:
        """
        도움말 메시지

        Returns:
            str: 도움말
        """
        return """
🤖 KakaoBot 명령어 도움말

📅 일정 관리
  • 등록 [날짜] [내용]
    예: 등록 250121 팀 회의
  • 일정 [날짜] - 특정 날짜 일정 조회
  • 삭제 [날짜] - 특정 날짜 일정 삭제
  • 금주일정 - 이번 주 일정 조회
  • 차주일정 - 다음 주 일정 조회
  • 일정목록 - 다가오는 일정 조회
  • 일정통계 - 일정 통계

🔗 링크 요약
  • 유튜브 URL 전송 - 자동 요약
  • 웹페이지 URL 전송 - 자동 요약

🤖 AI 기능
  • !ai [질문] - AI에게 질문하기

💡 기타
  • 도움말 - 이 메시지 보기
        """.strip()

    def _parse_short_date(self, date_str: str) -> date:
        """
        짧은 날짜 문자열 파싱 (YYMMDD 형식)

        Args:
            date_str: 날짜 문자열 (YYMMDD 또는 YY-MM-DD)

        Returns:
            date: 파싱된 날짜
        """
        try:
            # 하이픈 제거
            date_str = date_str.replace('-', '')

            if len(date_str) == 6:
                # YYMMDD 형식
                year = int('20' + date_str[:2])
                month = int(date_str[2:4])
                day = int(date_str[4:6])
                return date(year, month, day)
            else:
                raise ValueError("날짜 형식이 올바르지 않습니다.")

        except (ValueError, IndexError) as e:
            raise ValidationError(f"잘못된 날짜 형식입니다: {date_str}. YYMMDD 형식을 사용하세요. (예: 250121)")

    def _parse_date(self, date_str: str) -> date:
        """
        날짜 문자열 파싱

        Args:
            date_str: 날짜 문자열 (YYYY-MM-DD)

        Returns:
            date: 파싱된 날짜
        """
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError(f"잘못된 날짜 형식입니다: {date_str}. YYYY-MM-DD 형식을 사용하세요.")

    def _parse_time(self, time_str: str):
        """
        시간 문자열 파싱

        Args:
            time_str: 시간 문자열 (HH:MM)

        Returns:
            time: 파싱된 시간
        """
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            raise ValidationError(f"잘못된 시간 형식입니다: {time_str}. HH:MM 형식을 사용하세요.")

    async def _handle_image_generation(self, chat, prompt: str) -> Optional[str]:
        """이미지 생성 처리"""
        try:
            image_bytes, error_msg = await self.image_service.generate_image(prompt)

            if image_bytes:
                # 이미지 전송
                chat.reply_media([image_bytes])
                return None  # reply_media로 이미 전송했으므로 None 반환
            else:
                return f"❌ {error_msg}"

        except Exception as e:
            self.logger.error("image_generation_failed", error=str(e))
            return f"❌ 이미지 생성 실패: {str(e)}"

    async def _handle_image_analysis(self, chat) -> str:
        """이미지 분석 처리 (답장 메시지의 이미지)"""
        try:
            if not hasattr(chat.message, 'source_id') or not chat.message.source_id:
                return "❌ 이미지가 포함된 메시지에 답장으로 사용해주세요."

            source = chat.get_source()

            if not hasattr(source, 'image') or not source.image:
                return "❌ 답장한 메시지에 이미지가 없습니다."

            photo_url = source.image.url[0]
            result = await self.image_service.analyze_image(photo_url)

            return f"📊 이미지 분석 결과:\n\n{result}"

        except Exception as e:
            self.logger.error("image_analysis_failed", error=str(e))
            return f"❌ 이미지 분석 실패: {str(e)}"

    async def _handle_coin_price(self, symbol: str, user_id: str) -> str:
        """코인 가격 조회"""
        try:
            return await self.crypto_service.get_coin_price(symbol, user_id)
        except Exception as e:
            return f"❌ 코인 조회 실패: {str(e)}"

    async def _handle_my_coins(self, user_id: str) -> str:
        """내 코인 조회"""
        try:
            return await self.crypto_service.get_my_coins(user_id)
        except Exception as e:
            return f"❌ 내 코인 조회 실패: {str(e)}"

    async def _handle_kimchi_premium(self) -> str:
        """김치 프리미엄 조회"""
        try:
            return await self.crypto_service.get_kimchi_premium()
        except Exception as e:
            return f"❌ 김치 프리미엄 조회 실패: {str(e)}"

    async def _handle_coin_add(self, user_id: str, param: str) -> str:
        """코인 등록"""
        try:
            parts = param.split()
            if len(parts) != 3:
                return "❌ 형식: !코인등록 코인심볼 보유수량 평균단가\n예: !코인등록 BTC 1.5 50000000"

            symbol = parts[0]
            amount = float(parts[1].replace(',', ''))
            average = float(parts[2].replace(',', ''))

            return await self.crypto_service.add_coin(user_id, symbol, amount, average)

        except ValueError:
            return "❌ 숫자 형식이 올바르지 않습니다."
        except Exception as e:
            return f"❌ 코인 등록 실패: {str(e)}"

    async def _handle_coin_remove(self, user_id: str, symbol: str) -> str:
        """코인 삭제"""
        try:
            return await self.crypto_service.remove_coin(user_id, symbol)
        except Exception as e:
            return f"❌ 코인 삭제 실패: {str(e)}"

    async def _handle_stock_chart(self, chat, query: str) -> Optional[str]:
        """주식 차트 생성"""
        try:
            image_bytes = await self.stock_service.create_stock_chart(query)

            if image_bytes:
                chat.reply_media([image_bytes])
                return None
            else:
                return "❌ 주식 차트를 생성할 수 없습니다."

        except Exception as e:
            return f"❌ 주식 차트 생성 실패: {str(e)}"

    async def _handle_tts(self, chat, text: str) -> Optional[str]:
        """TTS 음성 생성"""
        try:
            # 옵션 파싱
            clean_text, voice_name, language_code = self.tts_service.parse_tts_options(text)

            # TTS 생성
            filepath = await self.tts_service.generate_tts(clean_text, voice_name, language_code)

            # 음성 파일 전송 (iris의 reply_audio 사용 필요)
            # 현재는 파일 경로만 반환
            return f"🔊 음성이 생성되었습니다: {filepath}\n(음성 파일 전송 기능은 추후 구현 예정)"

        except Exception as e:
            return f"❌ TTS 생성 실패: {str(e)}"

    async def _handle_rag_query(self, query: str) -> str:
        """RAG 검색 기반 질문 응답"""
        try:
            self.logger.info("rag_query_request", query=query[:50])
            response = await self.rag_service.answer_with_rag(query, self.ai_service)
            return f"🔍 RAG 검색 결과:\n\n{response}"

        except Exception as e:
            self.logger.error("rag_query_failed", error=str(e))
            return f"❌ RAG 검색 실패: {str(e)}"

    async def _handle_multi_llm_query(self, query: str) -> str:
        """Multi-LLM 질문 처리"""
        try:
            self.logger.info("multi_llm_query_request", query=query[:50])
            response = await self.multi_llm_service.generate_with_fallback(query)
            return f"🤖 AI 응답:\n\n{response}"

        except Exception as e:
            self.logger.error("multi_llm_query_failed", error=str(e))
            return f"❌ AI 응답 실패: {str(e)}"

    async def _handle_crypto_analysis(self, coin_id: str) -> str:
        """고급 암호화폐 분석 (기술 지표)"""
        try:
            self.logger.info("crypto_analysis_request", coin_id=coin_id)
            report = await self.crypto_advanced_service.get_advanced_analysis(coin_id.lower())
            return report

        except Exception as e:
            self.logger.error("crypto_analysis_failed", error=str(e))
            return f"❌ 암호화폐 분석 실패: {str(e)}"

    async def _handle_web_crawl(self, url: str) -> str:
        """웹페이지 크롤링"""
        try:
            self.logger.info("web_crawl_request", url=url[:100])
            content = await self.playwright_service.fetch_page_multi_strategy(url, max_chars=2000)

            if content:
                return f"🌐 웹페이지 내용:\n\n{content[:1500]}\n\n... (총 {len(content)}자)"
            else:
                return "❌ 웹페이지를 크롤링할 수 없습니다."

        except Exception as e:
            self.logger.error("web_crawl_failed", error=str(e))
            return f"❌ 웹 크롤링 실패: {str(e)}"
