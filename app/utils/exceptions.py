"""
Custom Exceptions
애플리케이션 전용 예외 정의
"""
from typing import Optional, Any


class KakaoBotException(Exception):
    """Base exception for all custom exceptions"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class DatabaseError(KakaoBotException):
    """Database related errors"""
    pass


class ConnectionError(DatabaseError):
    """Database connection errors"""
    pass


class QueryError(DatabaseError):
    """Database query errors"""
    pass


class NotFoundError(KakaoBotException):
    """Resource not found errors"""
    pass


class EventNotFoundError(NotFoundError):
    """Event not found"""
    pass


class UserNotFoundError(NotFoundError):
    """User not found"""
    pass


class RoomNotFoundError(NotFoundError):
    """Room not found"""
    pass


class ValidationError(KakaoBotException):
    """Validation errors"""
    pass


class AuthenticationError(KakaoBotException):
    """Authentication errors"""
    pass


class AuthorizationError(KakaoBotException):
    """Authorization errors"""
    pass


class ExternalServiceError(KakaoBotException):
    """External service errors"""
    pass


class AIServiceError(ExternalServiceError):
    """AI service errors"""
    pass


class KakaoAPIError(ExternalServiceError):
    """Kakao API errors"""
    pass


class GoogleAPIError(ExternalServiceError):
    """Google API errors"""
    pass


class RateLimitError(KakaoBotException):
    """Rate limit exceeded"""
    pass


class ConfigurationError(KakaoBotException):
    """Configuration errors"""
    pass
