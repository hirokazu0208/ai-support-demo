from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """プロセスが応答可能かを返す（liveness）。DB 接続は確認しない。"""
    return HealthResponse(status="ok")
