"""TracePilot Phase 1 API 路由。"""

from fastapi import APIRouter, FastAPI, Request

from tracepilot import __version__
from tracepilot.schemas.health import HealthResponse
from tracepilot.schemas.investigation import (
    ApproveActionRequest,
    ApproveActionResponse,
    InvestigateRequest,
    InvestigateResponse,
)
from tracepilot.services.investigation_service import InvestigationService

router = APIRouter()


# 从应用状态中读取服务实例，保证路由层只负责协议转换与响应编排。
def get_investigation_service(request: Request) -> InvestigationService:
    app: FastAPI = request.app
    return app.state.investigation_service


# 返回健康状态，满足服务探活和 Swagger 基础验证需要。
@router.get("/health", response_model=HealthResponse, tags=["system"], summary="健康检查")
def health() -> HealthResponse:
    return HealthResponse(service="TracePilot", status="ok", version=__version__)


# 创建排障会话并返回 Phase 1 约定的响应骨架。
@router.post(
    "/investigate",
    response_model=InvestigateResponse,
    tags=["investigation"],
    summary="发起排障",
)
def investigate(request: InvestigateRequest, http_request: Request) -> InvestigateResponse:
    service = get_investigation_service(http_request)
    return service.investigate(request)


# 审批 guarded 动作并返回更新后的状态对象骨架。
@router.post(
    "/actions/approve",
    response_model=ApproveActionResponse,
    tags=["actions"],
    summary="审批动作",
)
def approve_action(request: ApproveActionRequest, http_request: Request) -> ApproveActionResponse:
    service = get_investigation_service(http_request)
    return service.approve_action(request)
