"""
Utils Package
공통 유틸리티 export
"""
from .database import DatabaseManager, db_manager
from .logger import get_logger, setup_logging, LoggerMixin
from .room_storage import RoomStorage, room_storage
from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    ai_service_breaker,
    database_breaker,
    external_api_breaker
)
from .exceptions import (
    KakaoBotException,
    ValidationError,
    EventNotFoundError,
    DatabaseError,
    ConnectionError,
    QueryError,
    NotFoundError,
    UserNotFoundError,
    RoomNotFoundError,
    AuthenticationError,
    AuthorizationError,
    ExternalServiceError,
    AIServiceError,
    KakaoAPIError,
    GoogleAPIError,
    RateLimitError,
    ConfigurationError
)

__all__ = [
    # Database
    'DatabaseManager',
    'db_manager',

    # Logging
    'get_logger',
    'setup_logging',
    'LoggerMixin',

    # Room Storage
    'RoomStorage',
    'room_storage',

    # Circuit Breaker
    'CircuitBreaker',
    'CircuitState',
    'ai_service_breaker',
    'database_breaker',
    'external_api_breaker',

    # Exceptions
    'KakaoBotException',
    'ValidationError',
    'EventNotFoundError',
    'DatabaseError',
    'ConnectionError',
    'QueryError',
    'NotFoundError',
    'UserNotFoundError',
    'RoomNotFoundError',
    'AuthenticationError',
    'AuthorizationError',
    'ExternalServiceError',
    'AIServiceError',
    'KakaoAPIError',
    'GoogleAPIError',
    'RateLimitError',
    'ConfigurationError',
]
