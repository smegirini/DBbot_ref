"""
Health Check API
헬스 체크 및 상태 확인 엔드포인트
"""
from fastapi import APIRouter, Depends, status
from datetime import datetime
from typing import Dict, Any

from app.utils import get_db, DatabaseManager
from app.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK)
@router.get("/", status_code=status.HTTP_200_OK)
async def health_check(
    db: DatabaseManager = Depends(get_db)
) -> Dict[str, Any]:
    """
    Health check endpoint

    Returns:
        Dict[str, Any]: Health status
    """
    # Check database health
    db_healthy = await db.health_check()

    # Overall health status
    is_healthy = db_healthy

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.now().isoformat(),
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "checks": {
            "database": "ok" if db_healthy else "failed"
        }
    }


@router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness_check() -> Dict[str, str]:
    """
    Readiness check for Kubernetes/container orchestration

    Returns:
        Dict[str, str]: Readiness status
    """
    return {
        "status": "ready",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness_check() -> Dict[str, str]:
    """
    Liveness check for Kubernetes/container orchestration

    Returns:
        Dict[str, str]: Liveness status
    """
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    }
