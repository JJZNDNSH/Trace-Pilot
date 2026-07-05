"""健康检查接口模型。"""

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """健康检查响应。"""

    # 允许模型稳定序列化，保持接口输出风格统一。
    model_config = ConfigDict(use_enum_values=True)

    # 服务名，帮助调用方确认当前响应来自哪个应用。
    service: str = Field(..., description="服务名。")
    # 服务状态，供探活和监控直接消费。
    status: str = Field(..., description="服务状态。")
    # 版本号，便于联调时确认当前运行的接口版本。
    version: str = Field(..., description="版本号。")
