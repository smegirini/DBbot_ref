"""
Circuit Breaker Pattern
외부 서비스 호출 실패 시 회로 차단기 패턴 구현
"""
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps
import structlog

from app.config import settings

logger = structlog.get_logger()


class CircuitState(str, Enum):
    """Circuit Breaker 상태"""
    CLOSED = "closed"  # 정상 동작
    OPEN = "open"  # 회로 차단 (요청 거부)
    HALF_OPEN = "half_open"  # 복구 시도


class CircuitBreaker:
    """
    Circuit Breaker 구현

    외부 서비스 호출 실패가 임계값을 초과하면 일정 시간 동안 호출을 차단합니다.

    Example:
        circuit_breaker = CircuitBreaker(
            fail_threshold=5,
            recovery_timeout=30
        )

        @circuit_breaker
        async def call_external_api():
            # ... API 호출
            pass
    """

    def __init__(
        self,
        fail_threshold: Optional[int] = None,
        recovery_timeout: Optional[int] = None,
        expected_exception: type[Exception] = Exception
    ):
        """
        Initialize Circuit Breaker

        Args:
            fail_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to catch
        """
        self.fail_threshold = fail_threshold or settings.circuit_breaker.fail_threshold
        self.recovery_timeout = recovery_timeout or settings.circuit_breaker.recovery_timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "circuit_breaker_half_open",
                    failure_count=self._failure_count
                )
        return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if not self._last_failure_time:
            return False

        return (
            datetime.now() - self._last_failure_time
            >= timedelta(seconds=self.recovery_timeout)
        )

    def _on_success(self):
        """Handle successful call"""
        self._failure_count = 0
        self._last_failure_time = None
        if self._state != CircuitState.CLOSED:
            logger.info("circuit_breaker_closed")
            self._state = CircuitState.CLOSED

    def _on_failure(self):
        """Handle failed call"""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        logger.warning(
            "circuit_breaker_failure",
            failure_count=self._failure_count,
            threshold=self.fail_threshold
        )

        if self._failure_count >= self.fail_threshold:
            self._state = CircuitState.OPEN
            logger.error(
                "circuit_breaker_opened",
                failure_count=self._failure_count,
                recovery_timeout=self.recovery_timeout
            )

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker"""
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if self.state == CircuitState.OPEN:
                logger.warning(
                    "circuit_breaker_call_blocked",
                    function=func.__name__
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN for {func.__name__}"
                )

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise
            except Exception as e:
                # Unexpected exceptions don't count as failures
                logger.error(
                    "circuit_breaker_unexpected_error",
                    function=func.__name__,
                    error=str(e)
                )
                raise

        return wrapper

    def reset(self):
        """Manually reset circuit breaker"""
        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED
        logger.info("circuit_breaker_manually_reset")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass


# Global circuit breakers for common services
ai_service_breaker = CircuitBreaker(
    fail_threshold=5,
    recovery_timeout=30,
    expected_exception=Exception
)

database_breaker = CircuitBreaker(
    fail_threshold=3,
    recovery_timeout=10,
    expected_exception=Exception
)

external_api_breaker = CircuitBreaker(
    fail_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)
