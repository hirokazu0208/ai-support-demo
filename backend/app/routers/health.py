import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """プロセスが応答可能かを返す（liveness）。DB 接続は確認しない。"""
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness(
    response: Response, db: Annotated[Session, Depends(get_db)]
) -> ReadinessResponse:
    """DB に接続できるかを返す（readiness）。migration の適用状況は確認しない。"""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # 例外の詳細や接続先はレスポンスに含めず、サーバーログにのみ出力する
        logger.exception("Database readiness check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unavailable")
    return ReadinessResponse(status="ok")
