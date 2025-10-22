"""
KakaoBot Calendar Service
FastAPI 애플리케이션 엔트리포인트
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import time

from app.config import settings
from app.utils import setup_logging, get_logger, db_manager, KakaoBotException
from app.api import health_router, events_router

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager

    Handles startup and shutdown events
    """
    # Startup
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        env=settings.app_env,
        debug=settings.app_debug
    )

    # Initialize database connection pool
    try:
        await db_manager.create_pool()
        logger.info("database_connection_pool_initialized")
    except Exception as e:
        logger.error("database_pool_initialization_failed", error=str(e))
        raise

    logger.info("application_started")

    yield

    # Shutdown
    logger.info("application_shutting_down")

    # Close database connection pool
    try:
        await db_manager.close_pool()
        logger.info("database_connection_pool_closed")
    except Exception as e:
        logger.error("database_pool_closure_failed", error=str(e))

    logger.info("application_stopped")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="KakaoTalk Bot Calendar Service - Ubuntu Migration",
    version="2.0.0",
    docs_url="/docs" if settings.app_debug else None,
    redoc_url="/redoc" if settings.app_debug else None,
    lifespan=lifespan
)


# Middleware Configuration
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all HTTP requests

    Args:
        request: HTTP request
        call_next: Next middleware/handler

    Returns:
        Response
    """
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Log request
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=f"{duration:.3f}s"
    )

    return response


# Exception Handlers
@app.exception_handler(KakaoBotException)
async def kakaobot_exception_handler(request: Request, exc: KakaoBotException):
    """
    Handle custom KakaoBot exceptions

    Args:
        request: HTTP request
        exc: KakaoBot exception

    Returns:
        JSON error response
    """
    logger.error(
        "kakaobot_exception",
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        path=request.url.path
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors

    Args:
        request: HTTP request
        exc: Validation exception

    Returns:
        JSON error response
    """
    logger.warning(
        "validation_error",
        errors=exc.errors(),
        path=request.url.path
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "ValidationError",
            "message": "Request validation failed",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle general exceptions

    Args:
        request: HTTP request
        exc: General exception

    Returns:
        JSON error response
    """
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "InternalServerError",
            "message": "An unexpected error occurred"
        }
    )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint

    Returns:
        Welcome message
    """
    return {
        "message": "KakaoBot Calendar Service API",
        "version": "2.0.0",
        "environment": settings.app_env,
        "docs": "/docs" if settings.app_debug else "Documentation disabled in production"
    }


# Include routers
app.include_router(health_router)
app.include_router(events_router, prefix="/api/v1")


# Run application (for development)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_development,
        log_level=settings.logging.level.lower()
    )
