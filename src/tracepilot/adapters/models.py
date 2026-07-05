"""TracePilot adapter 层数据模型定义。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AlertRecord(BaseModel):
    """告警记录。"""

    # 告警唯一标识，用于关联同一条告警事件。
    alert_id: str = Field(..., description="告警唯一标识。")
    # 场景标识，用于声明该记录属于哪个 mock 场景。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称，用于标记告警所属服务。
    service: str = Field(..., description="服务名称。")
    # 告警名称，用于描述触发的监控规则。
    name: str = Field(..., description="告警名称。")
    # 告警级别，用于区分影响严重程度。
    severity: str = Field(..., description="告警级别。")
    # 告警状态，用于区分 firing 或 resolved。
    status: str = Field(..., description="告警状态。")
    # 触发时间，用于描述告警开始出现的时间点。
    fired_at: str = Field(..., description="触发时间。")
    # 恢复时间，用于描述告警结束时间，未恢复时为空。
    resolved_at: str | None = Field(default=None, description="恢复时间。")
    # 告警摘要，用于给排障流程提供简洁上下文。
    summary: str = Field(..., description="告警摘要。")
    # 标签集合，用于表达环境、集群和业务线等附加信息。
    labels: dict[str, str] = Field(default_factory=dict, description="标签集合。")


class LogRecord(BaseModel):
    """日志记录。"""

    # 日志时间，用于保持时间线顺序。
    timestamp: str = Field(..., description="日志时间。")
    # 场景标识，用于声明该记录属于哪个 mock 场景。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称，用于标记日志来源服务。
    service: str = Field(..., description="服务名称。")
    # 实例名称，用于标记具体产生日志的节点。
    instance: str = Field(..., description="实例名称。")
    # 日志级别，用于区分错误、告警和普通信息。
    level: str = Field(..., description="日志级别。")
    # Trace 标识，用于在调用链上串联相关请求。
    trace_id: str | None = Field(default=None, description="Trace 标识。")
    # 日志消息，用于描述发生了什么以及为什么重要。
    message: str = Field(..., description="日志消息。")
    # 结构化字段，用于补充错误码、版本等上下文。
    fields: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="结构化字段。",
    )


class MetricPoint(BaseModel):
    """单个指标点。"""

    # 采样时间，用于描述指标采样时刻。
    timestamp: str = Field(..., description="采样时间。")
    # 场景标识，用于声明该记录属于哪个 mock 场景。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称，用于标记指标所属服务。
    service: str = Field(..., description="服务名称。")
    # 指标名称，用于区分错误率、延迟和资源利用率等。
    metric_name: str = Field(..., description="指标名称。")
    # 指标值，用于表达当前采样结果。
    value: float = Field(..., description="指标值。")
    # 指标单位，用于解释当前值的业务含义。
    unit: str = Field(..., description="指标单位。")
    # 标签集合，用于描述维度信息，便于筛选和聚合。
    labels: dict[str, str] = Field(default_factory=dict, description="标签集合。")


class ChangeRecord(BaseModel):
    """变更记录。"""

    # 变更唯一标识，用于关联一次发布或配置变更。
    change_id: str = Field(..., description="变更唯一标识。")
    # 场景标识，用于声明该记录属于哪个 mock 场景。
    scenario_id: str = Field(..., description="场景标识。")
    # 服务名称，用于标记变更影响的服务。
    service: str = Field(..., description="服务名称。")
    # 变更类型，用于区分发布、配置或数据库变更。
    change_type: str = Field(..., description="变更类型。")
    # 变更时间，用于和告警、日志建立因果关系。
    changed_at: str = Field(..., description="变更时间。")
    # 执行人，用于记录是谁触发了变更。
    operator: str = Field(..., description="执行人。")
    # 版本号，用于标记发布或脚本版本。
    version: str | None = Field(default=None, description="版本号。")
    # 变更摘要，用于快速理解本次变更内容。
    summary: str = Field(..., description="变更摘要。")
    # 变更详情，用于补充影响范围和配置内容。
    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="变更详情。",
    )


class TicketRecord(BaseModel):
    """工单记录。"""

    # 工单唯一标识，用于追踪处置过程。
    ticket_id: str = Field(..., description="工单唯一标识。")
    # 场景标识，用于声明该记录属于哪个 mock 场景。
    scenario_id: str = Field(..., description="场景标识。")
    # 工单标题，用于概括当前故障现象。
    title: str = Field(..., description="工单标题。")
    # 工单状态，用于描述当前处理进度。
    status: str = Field(..., description="工单状态。")
    # 工单优先级，用于反映处理紧急程度。
    priority: str = Field(..., description="工单优先级。")
    # 创建时间，用于记录工单首次登记时间。
    created_at: str = Field(..., description="创建时间。")
    # 更新时间，用于记录最后一次处理时间。
    updated_at: str = Field(..., description="更新时间。")
    # 责任团队，用于标记当前归属方。
    owner_team: str = Field(..., description="责任团队。")
    # 工单描述，用于补充用户影响和排查过程。
    description: str = Field(..., description="工单描述。")


class RunbookRecord(BaseModel):
    """Runbook 记录。"""

    # 场景标识，用于声明该记录属于哪个 mock 场景。
    scenario_id: str = Field(..., description="场景标识。")
    # Runbook 标题，用于概括适用主题。
    title: str = Field(..., description="Runbook 标题。")
    # 服务名称，用于标记该文档主要适用的服务。
    service: str = Field(..., description="服务名称。")
    # Markdown 原文，用于保留完整操作说明。
    content: str = Field(..., description="Markdown 原文。")


class CMDBRecord(BaseModel):
    """CMDB 记录。"""

    # 服务名称，用于标记当前配置项对应的服务。
    service: str = Field(..., description="服务名称。")
    # 场景标识，用于声明该记录属于哪个 mock 场景。
    scenario_id: str = Field(..., description="场景标识。")
    # 所属团队，用于明确当前服务责任归属。
    owner_team: str = Field(..., description="所属团队。")
    # 运行环境，用于标记是生产还是预发等环境。
    environment: str = Field(..., description="运行环境。")
    # 仓库地址，用于辅助定位代码变更来源。
    repository: str = Field(..., description="仓库地址。")
    # 上游依赖，用于描述该服务调用哪些系统。
    upstreams: list[str] = Field(default_factory=list, description="上游依赖。")
    # 下游依赖，用于描述哪些系统依赖该服务。
    downstreams: list[str] = Field(default_factory=list, description="下游依赖。")
    # 值班组，用于表示当前默认协作团队。
    oncall_team: str = Field(..., description="值班组。")
    # 补充说明，用于保留容量、SLO 等额外信息。
    notes: str | None = Field(default=None, description="补充说明。")
