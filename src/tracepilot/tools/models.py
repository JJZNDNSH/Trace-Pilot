"""TracePilot 工具层模型定义。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tracepilot.domain.enums import ActionRiskLevel


class ToolCallStatus(str, Enum):
    """工具调用状态枚举。"""

    SUCCESS = "success"
    FALLBACK = "fallback"
    FAILED = "failed"
    GUARDED = "guarded"
    DENIED = "denied"


class SearchAlertsInput(BaseModel):
    """`search_alerts` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于定位要读取的 mock 告警数据目录。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称过滤条件，用于只返回某个服务的告警。
    service: str | None = Field(default=None, description="服务名称过滤条件。")
    # 告警级别过滤条件，用于只关注 critical 或 warning 等级。
    severity: str | None = Field(default=None, description="告警级别过滤条件。")
    # 告警状态过滤条件，用于过滤 firing 或 resolved。
    status: str | None = Field(default=None, description="告警状态过滤条件。")
    # 关键字过滤条件，用于在告警名称和摘要里做模糊检索。
    keyword: str | None = Field(default=None, description="关键字过滤条件。")
    # 返回条数上限，用于控制工具输出体积。
    limit: int = Field(default=20, ge=1, le=200, description="返回条数上限。")


class SearchLogsInput(BaseModel):
    """`search_logs` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于定位要读取的 mock 日志数据目录。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称过滤条件，用于缩小日志来源范围。
    service: str | None = Field(default=None, description="服务名称过滤条件。")
    # 日志级别过滤条件，用于聚焦 ERROR 或 WARN 等日志。
    level: str | None = Field(default=None, description="日志级别过滤条件。")
    # 关键字过滤条件，用于在日志消息里检索异常模式。
    keyword: str | None = Field(default=None, description="关键字过滤条件。")
    # Trace 标识过滤条件，用于串联同一条请求链路。
    trace_id: str | None = Field(default=None, description="Trace 标识过滤条件。")
    # 返回条数上限，用于控制长日志场景的输出规模。
    limit: int = Field(default=50, ge=1, le=500, description="返回条数上限。")


class QueryMetricsInput(BaseModel):
    """`query_metrics` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于定位要读取的 mock 指标数据目录。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称过滤条件，用于只看某个服务的指标。
    service: str | None = Field(default=None, description="服务名称过滤条件。")
    # 指标名称过滤条件，用于聚焦错误率、延迟或资源类指标。
    metric_name: str | None = Field(default=None, description="指标名称过滤条件。")
    # 标签过滤条件，用于按 endpoint、status 等维度筛选数据点。
    label_filters: dict[str, str] = Field(default_factory=dict, description="标签过滤条件。")
    # 返回条数上限，用于控制指标点数量。
    limit: int = Field(default=100, ge=1, le=500, description="返回条数上限。")


class GetRecentChangesInput(BaseModel):
    """`get_recent_changes` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于定位要读取的 mock 变更数据目录。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称过滤条件，用于仅查看指定服务的变更。
    service: str | None = Field(default=None, description="服务名称过滤条件。")
    # 变更类型过滤条件，用于区分 release、config 等变更。
    change_type: str | None = Field(default=None, description="变更类型过滤条件。")
    # 返回条数上限，用于控制时间线输出规模。
    limit: int = Field(default=20, ge=1, le=200, description="返回条数上限。")


class SearchTicketsInput(BaseModel):
    """`search_tickets` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于定位要读取的 mock 工单数据目录。
    scenario_id: str = Field(..., description="场景标识。")
    # 工单状态过滤条件，用于只看 investigating 或 resolved 等状态。
    status: str | None = Field(default=None, description="工单状态过滤条件。")
    # 工单优先级过滤条件，用于聚焦 P1 或 P2 工单。
    priority: str | None = Field(default=None, description="工单优先级过滤条件。")
    # 关键字过滤条件，用于在标题和描述中检索问题线索。
    keyword: str | None = Field(default=None, description="关键字过滤条件。")
    # 返回条数上限，用于控制输出规模。
    limit: int = Field(default=20, ge=1, le=200, description="返回条数上限。")


class GetServiceDependenciesInput(BaseModel):
    """`get_service_dependencies` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于定位要读取的 mock CMDB 数据目录。
    scenario_id: str = Field(..., description="场景标识。")


class SearchRunbooksInput(BaseModel):
    """`search_runbooks` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于定位要读取的 mock Runbook 文档。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称过滤条件，用于按 Runbook 适用服务做匹配。
    service: str | None = Field(default=None, description="服务名称过滤条件。")
    # 关键字过滤条件，用于在标题和正文里检索排障说明。
    keyword: str | None = Field(default=None, description="关键字过滤条件。")


class GetIncidentTimelineInput(BaseModel):
    """`get_incident_timeline` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于定位要汇总的 mock 事件数据目录。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称过滤条件，用于从多源事件中只保留目标服务。
    service: str | None = Field(default=None, description="服务名称过滤条件。")
    # 是否纳入日志事件，用于在需要时裁剪时间线噪音。
    include_logs: bool = Field(default=True, description="是否纳入日志事件。")
    # 是否纳入变更事件，用于控制是否呈现发布和配置时间点。
    include_changes: bool = Field(default=True, description="是否纳入变更事件。")
    # 是否纳入告警事件，用于控制是否呈现监控触发点。
    include_alerts: bool = Field(default=True, description="是否纳入告警事件。")
    # 是否纳入工单事件，用于控制是否呈现人工处理时间点。
    include_tickets: bool = Field(default=True, description="是否纳入工单事件。")
    # 返回条数上限，用于控制汇总时间线的长度。
    limit: int = Field(default=100, ge=1, le=500, description="返回条数上限。")


class RestartServiceInput(BaseModel):
    """`restart_service` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于在演示或评测时关联当前 mock 场景。
    scenario_id: str | None = Field(default=None, description="场景标识。")
    # 服务名称，用于声明将对哪个服务执行重启动作。
    service: str = Field(..., description="服务名称。")
    # 目标环境，用于声明该动作作用在哪个环境。
    environment: str = Field(..., description="目标环境。")
    # 动作原因，用于记录为什么建议当前执行动作。
    reason: str = Field(..., description="动作原因。")


class RollbackReleaseInput(BaseModel):
    """`rollback_release` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于在演示或评测时关联当前 mock 场景。
    scenario_id: str | None = Field(default=None, description="场景标识。")
    # 服务名称，用于声明将对哪个服务执行回滚动作。
    service: str = Field(..., description="服务名称。")
    # 目标环境，用于声明该动作作用在哪个环境。
    environment: str = Field(..., description="目标环境。")
    # 目标版本，用于明确期望回退到哪个版本。
    target_version: str | None = Field(default=None, description="目标版本。")
    # 动作原因，用于记录为什么建议当前执行动作。
    reason: str = Field(..., description="动作原因。")


class ClearCacheInput(BaseModel):
    """`clear_cache` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于在演示或评测时关联当前 mock 场景。
    scenario_id: str | None = Field(default=None, description="场景标识。")
    # 服务名称，用于声明将对哪个服务执行清缓存动作。
    service: str = Field(..., description="服务名称。")
    # 目标环境，用于声明该动作作用在哪个环境。
    environment: str = Field(..., description="目标环境。")
    # 缓存名称，用于标记要清理的缓存区域或键空间。
    cache_name: str = Field(..., description="缓存名称。")
    # 动作原因，用于记录为什么建议当前执行动作。
    reason: str = Field(..., description="动作原因。")


class DisableFeatureFlagInput(BaseModel):
    """`disable_feature_flag` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于在演示或评测时关联当前 mock 场景。
    scenario_id: str | None = Field(default=None, description="场景标识。")
    # 服务名称，用于声明将对哪个服务关闭特性开关。
    service: str = Field(..., description="服务名称。")
    # 目标环境，用于声明该动作作用在哪个环境。
    environment: str = Field(..., description="目标环境。")
    # 特性开关名称，用于定位要关闭的功能开关。
    feature_flag: str = Field(..., description="特性开关名称。")
    # 动作原因，用于记录为什么建议当前执行动作。
    reason: str = Field(..., description="动作原因。")


class RerunHealthCheckInput(BaseModel):
    """`rerun_health_check` 输入参数。"""

    # 允许模型稳定序列化并禁止额外字段，避免工具参数在调用侧静默漂移。
    model_config = ConfigDict(extra="forbid")

    # 场景标识，用于在演示或评测时关联当前 mock 场景。
    scenario_id: str | None = Field(default=None, description="场景标识。")
    # 服务名称，用于声明将对哪个服务重跑健康检查。
    service: str = Field(..., description="服务名称。")
    # 目标环境，用于声明该动作作用在哪个环境。
    environment: str = Field(..., description="目标环境。")
    # 健康检查名称，用于标记要重跑的是哪个探针或检查项。
    check_name: str = Field(default="default", description="健康检查名称。")
    # 动作原因，用于补充为什么需要重跑健康检查。
    reason: str | None = Field(default=None, description="动作原因。")


class ToolGovernanceMarker(BaseModel):
    """工具风险治理标记。"""

    # 允许模型稳定序列化，便于接口和测试直接断言风险标记。
    model_config = ConfigDict(use_enum_values=True)

    # 风险等级，用于区分 auto、guarded、denied 三类动作治理语义。
    risk_level: ActionRiskLevel = Field(..., description="风险等级。")
    # 是否需要审批，用于前端或 CLI 呈现待审批动作。
    requires_approval: bool = Field(..., description="是否需要审批。")
    # 是否被策略拒绝，用于明确 denied 动作不会执行。
    denied: bool = Field(..., description="是否被策略拒绝。")
    # 风险原因，用于解释为什么当前工具被拦截或允许。
    reason: str | None = Field(default=None, description="风险原因。")


class ToolRuntimeMetadata(BaseModel):
    """工具运行时元数据。"""

    # 是否命中缓存，用于验证统一缓存能力是否生效。
    from_cache: bool = Field(..., description="是否命中缓存。")
    # 是否使用 fallback，用于表达主链路在异常时是否平滑降级。
    used_fallback: bool = Field(..., description="是否使用 fallback。")
    # 是否发生超时，用于区分普通异常和超时降级。
    timed_out: bool = Field(..., description="是否发生超时。")
    # 调用耗时，用于沉淀工具延迟统计。
    latency_ms: int = Field(..., ge=0, description="调用耗时（毫秒）。")
    # 缓存键，用于调试时确认缓存隔离是否符合预期。
    cache_key: str | None = Field(default=None, description="缓存键。")


class ToolStatsSnapshot(BaseModel):
    """单个工具的统计快照。"""

    # 工具名称，用于标记当前快照属于哪个工具。
    tool_name: str = Field(..., description="工具名称。")
    # 总调用次数，用于衡量工具被使用的频率。
    total_calls: int = Field(..., ge=0, description="总调用次数。")
    # 成功次数，用于统计稳定成功的调用量。
    success_calls: int = Field(..., ge=0, description="成功次数。")
    # fallback 次数，用于统计降级执行的频率。
    fallback_calls: int = Field(..., ge=0, description="fallback 次数。")
    # 失败次数，用于统计未被 fallback 吞掉的错误。
    failed_calls: int = Field(..., ge=0, description="失败次数。")
    # 超时次数，用于统计工具超时的稳定性风险。
    timeout_calls: int = Field(..., ge=0, description="超时次数。")
    # 缓存命中次数，用于衡量缓存收益。
    cache_hits: int = Field(..., ge=0, description="缓存命中次数。")
    # guarded 次数，用于统计需要审批的动作被提出了多少次。
    guarded_calls: int = Field(..., ge=0, description="guarded 次数。")
    # denied 次数，用于统计被策略直接拒绝的动作数量。
    denied_calls: int = Field(..., ge=0, description="denied 次数。")
    # 平均耗时，用于观察工具调用延迟趋势。
    average_latency_ms: float = Field(..., ge=0.0, description="平均耗时（毫秒）。")


class ToolResponse(BaseModel):
    """统一工具返回结构。"""

    # 允许模型稳定序列化，便于接口和测试直接断言统一字段结构。
    model_config = ConfigDict(use_enum_values=True)

    # 工具名称，用于让调用方知道是哪一个工具返回了当前结果。
    tool_name: str = Field(..., description="工具名称。")
    # 调用状态，用于统一表达成功、fallback、guarded、denied 等结果。
    status: ToolCallStatus = Field(..., description="调用状态。")
    # 响应消息，用于向上层返回简洁的人类可读说明。
    message: str = Field(..., description="响应消息。")
    # 结构化数据载荷，用于承载查询结果或 mock 动作计划。
    data: Any = Field(default=None, description="结构化数据载荷。")
    # 错误信息，用于记录失败原因或 fallback 背景。
    error: str | None = Field(default=None, description="错误信息。")
    # 风险治理标记，用于表达审批和拒绝策略。
    governance: ToolGovernanceMarker = Field(..., description="风险治理标记。")
    # 运行时元数据，用于表达缓存、超时和耗时信息。
    runtime: ToolRuntimeMetadata = Field(..., description="运行时元数据。")
    # 调用后统计快照，用于验证 stats 是否按预期累积。
    stats: ToolStatsSnapshot = Field(..., description="调用后统计快照。")


class ToolSpec(BaseModel):
    """工具注册说明。"""

    # 工具名称，用于唯一标识注册表中的一个工具定义。
    name: str = Field(..., description="工具名称。")
    # 工具说明，用于帮助调用方理解该工具的职责。
    description: str = Field(..., description="工具说明。")
    # 风险等级，用于表达当前工具动作治理级别。
    risk_level: ActionRiskLevel = Field(..., description="风险等级。")
    # 超时时间，用于声明工具的执行上限。
    timeout_seconds: float = Field(..., gt=0, description="超时时间（秒）。")
    # 是否启用缓存，用于声明该工具是否参与统一缓存。
    cache_enabled: bool = Field(..., description="是否启用缓存。")
    # 缓存 TTL，用于声明缓存结果的有效期。
    cache_ttl_seconds: int = Field(..., ge=0, description="缓存 TTL（秒）。")
    # 入参 Schema，用于暴露明确的工具契约。
    input_schema: dict[str, Any] = Field(..., description="入参 Schema。")
