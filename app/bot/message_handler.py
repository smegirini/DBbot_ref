"""
Kakao Bot Message Handler
Iris 기반 WebSocket 메시지 처리
"""
import sys
from typing import Optional
from iris import Bot, ChatContext
from iris.decorators import has_param

from app.config import settings
from app.utils import get_logger, LoggerMixin, room_storage
from app.services import EventService, AIService
from app.services.command_service import CommandService
from app.services.youtube_service import YouTubeService
from app.services.notification_service import NotificationService
from app.repositories import EventRepository
from app.utils import db_manager


logger = get_logger(__name__)


class KakaoBotHandler(LoggerMixin):
    """
    Iris 기반 카카오톡 봇 핸들러

    WebSocket을 통해 Iris 서버와 연결하고
    메시지 이벤트를 처리합니다.
    """

    def __init__(self, iris_url: str):
        """
        Initialize Kakao Bot Handler

        Args:
            iris_url: Iris server URL (IP:PORT format)
        """
        self.iris_url = iris_url
        self.bot = Bot(iris_url)

        # Services 초기화 (나중에 async로 초기화)
        self.command_service: Optional[CommandService] = None
        self.event_service: Optional[EventService] = None
        self.youtube_service: Optional[YouTubeService] = None
        self.ai_service: Optional[AIService] = None
        self.notification_service: Optional[NotificationService] = None

        # 공유 이벤트 루프 설정 (핸들러 등록 전에 먼저 실행)
        self._setup_event_loop()

        # 이벤트 핸들러 등록
        self._register_handlers()

        self.logger.info(
            "kakaobot_handler_initialized",
            iris_url=iris_url
        )

    def _setup_event_loop(self):
        """공유 이벤트 루프 설정"""
        import asyncio
        import threading

        # 공유 이벤트 루프를 별도 스레드에서 실행
        self._loop = None
        self._loop_thread = None
        self._loop_ready = threading.Event()

        def start_background_loop():
            """백그라운드에서 이벤트 루프 실행"""
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            self._loop.run_forever()

        # 백그라운드 이벤트 루프 시작
        self._loop_thread = threading.Thread(target=start_background_loop, daemon=True)
        self._loop_thread.start()

        # 루프가 완전히 시작될 때까지 대기
        self._loop_ready.wait()

    def _register_handlers(self):
        """이벤트 핸들러 등록"""
        import asyncio

        def run_async(coro):
            """공유 이벤트 루프에서 코루틴 실행"""
            if self._loop is None:
                raise RuntimeError("Event loop not initialized")
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            # 결과를 기다리지 않고 바로 반환 (non-blocking)
            return future

        # 텍스트 메시지 이벤트
        @self.bot.on_event("message")
        def on_message(chat: ChatContext):
            run_async(self.handle_message(chat))

        # 모든 채팅 이벤트 (이미지, 동영상 등)
        @self.bot.on_event("chat")
        def on_chat(chat: ChatContext):
            run_async(self.handle_chat(chat))

        # 새 멤버 입장
        @self.bot.on_event("new_member")
        def on_new_member(chat: ChatContext):
            run_async(self.handle_new_member(chat))

        # 멤버 퇴장
        @self.bot.on_event("del_member")
        def on_del_member(chat: ChatContext):
            run_async(self.handle_del_member(chat))

        # 에러 핸들링
        @self.bot.on_event("error")
        def on_error(err):
            self.logger.error(
                "bot_event_error_occurred",
                error_event=err.event,
                exception=str(err.exception)
            )

    async def initialize_services(self):
        """
        서비스 초기화 (비동기)

        DB 연결 풀 생성 후 호출되어야 합니다.
        """
        try:
            # DB 연결 풀 생성
            await db_manager.create_pool()

            # Repository 초기화
            event_repo = EventRepository(db_manager)

            # Services 초기화
            self.event_service = EventService(event_repo)
            self.ai_service = AIService()
            self.youtube_service = YouTubeService(self.ai_service)

            # NotificationService 초기화
            self.notification_service = NotificationService(
                event_service=self.event_service
            )

            # CommandService 초기화 (NotificationService 포함)
            self.command_service = CommandService(
                event_service=self.event_service,
                youtube_service=self.youtube_service,
                ai_service=self.ai_service,
                notification_service=self.notification_service
            )

            self.logger.info("bot_services_initialized")

        except Exception as e:
            self.logger.error("bot_services_initialization_failed", error=str(e))
            raise

    async def handle_message(self, chat: ChatContext):
        """
        텍스트 메시지 처리

        Args:
            chat: ChatContext 객체
        """
        try:
            # room_name → room_id 매핑 자동 저장 (PyKV 영구 저장)
            room_storage.save_room(chat.room.name, chat.room.id)

            # 기본 정보 로깅
            self.logger.info(
                "message_received",
                room=chat.room.name,
                sender=chat.sender.name,
                command=chat.message.command,
                msg_preview=chat.message.msg[:50] if len(chat.message.msg) > 50 else chat.message.msg
            )

            # 명령어 처리 (ChatContext 전체 전달)
            if self.command_service:
                response = await self.command_service.process_command(chat)

                if response:
                    chat.reply(response)
                    self.logger.info(
                        "message_replied",
                        room=chat.room.name,
                        response_length=len(response)
                    )

        except Exception as e:
            self.logger.error(
                "message_handling_failed",
                room=chat.room.name if chat.room else "unknown",
                sender=chat.sender.name if chat.sender else "unknown",
                error=str(e)
            )
            chat.reply(f"❌ 오류가 발생했습니다: {str(e)}")

    async def handle_chat(self, chat: ChatContext):
        """
        모든 채팅 이벤트 처리 (이미지, 동영상 등)

        Args:
            chat: ChatContext 객체
        """
        try:
            # 이미지가 포함된 메시지
            if chat.message.image:
                self.logger.info(
                    "image_message_received",
                    room=chat.room.name,
                    sender=chat.sender.name,
                    image_count=len(chat.message.image.urls) if chat.message.image.urls else 0
                )
                # TODO: 이미지 처리 로직 추가

        except Exception as e:
            self.logger.error(
                "chat_handling_failed",
                error=str(e)
            )

    async def handle_new_member(self, chat: ChatContext):
        """
        새 멤버 입장 이벤트 처리

        Args:
            chat: ChatContext 객체
        """
        try:
            welcome_message = f"👋 환영합니다, {chat.sender.name}님!"
            chat.reply(welcome_message)

            self.logger.info(
                "new_member_joined",
                room=chat.room.name,
                member=chat.sender.name
            )

        except Exception as e:
            self.logger.error(
                "new_member_handling_failed",
                error=str(e)
            )

    async def handle_del_member(self, chat: ChatContext):
        """
        멤버 퇴장 이벤트 처리

        Args:
            chat: ChatContext 객체
        """
        try:
            self.logger.info(
                "member_left",
                room=chat.room.name,
                member=chat.sender.name
            )

        except Exception as e:
            self.logger.error(
                "del_member_handling_failed",
                error=str(e)
            )

    def run(self):
        """
        봇 실행 (블로킹)

        이 메서드는 블로킹되므로 메인 스레드에서 호출해야 합니다.
        """
        self.logger.info(
            "bot_starting",
            iris_url=self.iris_url
        )

        try:
            self.bot.run()
        except KeyboardInterrupt:
            self.logger.info("bot_stopped_by_user")
        except Exception as e:
            self.logger.error("bot_runtime_error", error=str(e))
            raise


# CLI 실행을 위한 진입점
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.bot.message_handler <IRIS_URL>")
        print("Example: python -m app.bot.message_handler 172.30.10.66:3000")
        sys.exit(1)

    iris_url = sys.argv[1]
    handler = KakaoBotHandler(iris_url)

    # 비동기 서비스 초기화
    import asyncio
    asyncio.run(handler.initialize_services())

    # 봇 실행 (블로킹)
    handler.run()
