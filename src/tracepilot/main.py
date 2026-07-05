"""TracePilot FastAPI 应用入口。"""

from fastapi import FastAPI

from tracepilot.api.routes import router
from tracepilot.services.investigation_service import InvestigationService


# 创建应用实例并只挂载当前阶段允许暴露的最小接口集合。
def create_app() -> FastAPI:
    app = FastAPI(
        title="TracePilot API",
        version="0.1.0",
        description="TracePilot Phase 1：领域模型、API 契约与路由骨架。",
    )
    # 在应用级别注入服务实例，保证路由无状态且测试易于隔离。
    app.state.investigation_service = InvestigationService()
    app.include_router(router)
    return app


# 导出应用对象，供 uvicorn 和测试直接加载。
app = create_app()
