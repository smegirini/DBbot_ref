"""
Application Configuration
Pydantic Settings를 사용한 타입 안전 설정 관리
"""
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import logging


class DatabaseSettings(BaseSettings):
    """데이터베이스 관련 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='DB_',
        extra='ignore'
    )

    host: str = Field(default='localhost', description='Database host')
    port: int = Field(default=3306, description='Database port')
    user: str = Field(description='Database user')
    password: str = Field(description='Database password')
    name: str = Field(description='Database name')

    # Connection Pool Settings
    pool_size: int = Field(default=20, description='Connection pool size')
    pool_recycle: int = Field(default=3600, description='Pool recycle time in seconds')

    # Timeout Settings
    connect_timeout: int = Field(default=10, ge=1, le=60)
    read_timeout: int = Field(default=60, ge=1, le=300)
    write_timeout: int = Field(default=60, ge=1, le=300)

    # Retry Settings
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_delay: int = Field(default=1, ge=0, le=10)

    @property
    def connection_url(self) -> str:
        """Database connection URL"""
        return f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='AZURE_OPENAI_',
        extra='ignore'
    )

    endpoint: Optional[str] = Field(default=None, description='Azure OpenAI endpoint')
    api_key: Optional[str] = Field(default=None, description='Azure OpenAI API key')
    model: str = Field(default='gpt-4', description='Model name')
    deployment_name: Optional[str] = Field(default=None, description='Deployment name')
    api_version: str = Field(default='2024-02-15-preview', description='API version')

    @property
    def is_configured(self) -> bool:
        """Check if Azure OpenAI is configured"""
        return bool(self.endpoint and self.api_key)


class GeminiSettings(BaseSettings):
    """Google Gemini 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='GEMINI_',
        extra='ignore'
    )

    api_key: Optional[str] = Field(default=None, description='Gemini API key')
    model: str = Field(default='gemini-2.0-flash-exp', description='Model name')
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=8192)

    @property
    def is_configured(self) -> bool:
        """Check if Gemini is configured"""
        return bool(self.api_key)


class AnthropicSettings(BaseSettings):
    """Anthropic Claude 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='ANTHROPIC_',
        extra='ignore'
    )

    api_key: Optional[str] = Field(default=None, description='Anthropic API key')
    model: str = Field(default='claude-3-5-sonnet-20241022', description='Model name')
    max_tokens: int = Field(default=4096, ge=1, le=8192)

    @property
    def is_configured(self) -> bool:
        """Check if Anthropic is configured"""
        return bool(self.api_key)


class GoogleServicesSettings(BaseSettings):
    """Google Services 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='GOOGLE_',
        extra='ignore'
    )

    application_credentials: Optional[str] = Field(default=None, description='Service account JSON path')
    spreadsheet_key: Optional[str] = Field(default=None, description='Google Spreadsheet key')
    calendar_id: Optional[str] = Field(default=None, description='Google Calendar ID')

    @property
    def scope(self) -> List[str]:
        """Google API scopes"""
        return [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/calendar'
        ]


class KakaoSettings(BaseSettings):
    """KakaoTalk API 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='KAKAO_',
        extra='ignore'
    )

    rest_api_key: Optional[str] = Field(default=None, description='Kakao REST API key')
    admin_key: Optional[str] = Field(default=None, description='Kakao Admin key')
    redirect_uri: str = Field(default='http://localhost:8000/oauth/kakao/callback')


class CircuitBreakerSettings(BaseSettings):
    """Circuit Breaker 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='CIRCUIT_BREAKER_',
        extra='ignore'
    )

    fail_threshold: int = Field(default=5, ge=1, le=20, description='Failure threshold')
    recovery_timeout: int = Field(default=30, ge=1, le=300, description='Recovery timeout in seconds')
    expected_exception: str = Field(default='Exception', description='Expected exception class name')


class LoggingSettings(BaseSettings):
    """로깅 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='LOG_',
        extra='ignore'
    )

    level: str = Field(default='INFO', description='Logging level')
    format: str = Field(default='json', description='Log format: json or text')
    file: Optional[str] = Field(default=None, description='Log file path')
    max_bytes: int = Field(default=10485760, description='Max log file size (10MB)')
    backup_count: int = Field(default=5, description='Number of backup files')

    @property
    def log_level(self) -> int:
        """Convert string level to logging constant"""
        return getattr(logging, self.level.upper(), logging.INFO)


class SecuritySettings(BaseSettings):
    """보안 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )

    secret_key: str = Field(min_length=32, description='Application secret key')
    allowed_hosts: str = Field(default='localhost,127.0.0.1')
    cors_origins: str = Field(default='http://localhost:3000')

    def get_allowed_hosts_list(self) -> List[str]:
        """Get allowed hosts as list"""
        return [h.strip() for h in self.allowed_hosts.split(',')]

    def get_cors_origins_list(self) -> List[str]:
        """Get CORS origins as list"""
        return [o.strip() for o in self.cors_origins.split(',')]


class SessionSettings(BaseSettings):
    """세션 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='SESSION_',
        extra='ignore'
    )

    timeout: int = Field(default=3600, ge=300, le=86400, description='Session timeout in seconds')
    cookie_secure: bool = Field(default=False, description='Use secure cookies')


class RateLimitSettings(BaseSettings):
    """Rate Limiting 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='RATE_LIMIT_',
        extra='ignore'
    )

    per_minute: int = Field(default=60, ge=1, le=1000)
    per_hour: int = Field(default=1000, ge=1, le=10000)


class CloudflareSettings(BaseSettings):
    """Cloudflare Tunnel 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='CLOUDFLARE_',
        extra='ignore'
    )

    tunnel_token: Optional[str] = Field(default=None, description='Cloudflare Tunnel token')
    tunnel_name: str = Field(default='kakaobot-calendar', description='Tunnel name')


class MonitoringSettings(BaseSettings):
    """모니터링 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='HEALTH_CHECK_',
        extra='ignore'
    )

    enabled: bool = Field(default=True, description='Enable health checks')
    interval: int = Field(default=30, ge=10, le=300, description='Health check interval')

    metrics_enabled: bool = Field(default=True, description='Enable metrics collection')


class NotificationSettings(BaseSettings):
    """알림 전송 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8'  ,
        extra='ignore'
    )

    helper_room_name: str = Field(default='도우미', description='Helper room name for receiving notifications')
    notification_room_names: str = Field(default='', description='Target room names (comma-separated)')

    def get_notification_rooms_list(self) -> List[str]:
        """Get notification room names as list"""
        if not self.notification_room_names:
            return []
        return [r.strip() for r in self.notification_room_names.split(',') if r.strip()]


class BackupSettings(BaseSettings):
    """백업 설정"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_prefix='BACKUP_',
        extra='ignore'
    )

    enabled: bool = Field(default=True, description='Enable backups')
    path: str = Field(default='/home/sh/Project/kakaobot/backups', description='Backup directory')
    retention_days: int = Field(default=30, ge=1, le=365, description='Backup retention in days')


class Settings(BaseSettings):
    """Main application settings"""
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

    # Application Settings
    app_name: str = Field(default='KakaoBot Calendar Service', description='Application name')
    app_env: str = Field(default='development', description='Environment: development, staging, production')
    app_debug: bool = Field(default=True, description='Debug mode')
    app_host: str = Field(default='127.0.0.1', description='Application host')
    app_port: int = Field(default=8000, ge=1000, le=65535, description='Application port')
    app_workers: int = Field(default=2, ge=1, le=16, description='Number of workers')

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    azure_openai: AzureOpenAISettings = Field(default_factory=AzureOpenAISettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    google_services: GoogleServicesSettings = Field(default_factory=GoogleServicesSettings)
    kakao: KakaoSettings = Field(default_factory=KakaoSettings)
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    cloudflare: CloudflareSettings = Field(default_factory=CloudflareSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    notification: NotificationSettings = Field(default_factory=NotificationSettings)
    backup: BackupSettings = Field(default_factory=BackupSettings)

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.app_env.lower() == 'production'

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.app_env.lower() == 'development'


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance

    Returns:
        Settings: Application settings
    """
    return Settings()


# Export for convenience
settings = get_settings()
