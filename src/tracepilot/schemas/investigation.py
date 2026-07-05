"""调查与审批接口模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from tracepilot.domain.enums import AgentType, FaultType, ToolType, UrgencyLevel
from tracepilot.domain.models import (
    ActionPlanRecord,
    AuditRecord,
    ConfirmedFact,
    ExecutionResultRecord,
    HypothesisRecord,
)
from tracepilot.domain.state import InvestigationState


class InvestigateRequest(BaseModel):
    """发起排障请求。"""

    # 允许模型稳定序列化，保持接口输出风格统一。
    model_config = ConfigDict(use_enum_values=True)

    # 用户标识，后续可用于画像和审计。
    user_id: str = Field(..., description="用户标识。")
    # 目标环境，标记故障发生在哪个环境。
    environment: str = Field(..., description="目标环境。")
    # 场景标识，便于和 mock 场景或评测 case 对齐。
    scenario_id: str | None = Field(default=None, description="场景标识。")
    # 故障描述，是当前阶段分类和规划的唯一输入。
    problem_statement: str = Field(..., min_length=1, description="故障描述。")


class InvestigateResponse(BaseModel):
    """排障请求响应。"""

    # 允许模型稳定序列化，保持接口输出风格统一。
    model_config = ConfigDict(use_enum_values=True)

    # 会话唯一标识，供审批或后续多轮排障继续引用。
    session_id: str = Field(..., description="会话唯一标识。")
    # 故障域分类，返回给调用方当前初步判断结果。
    fault_type: FaultType = Field(..., description="故障域分类。")
    # 紧急度，返回给调用方当前响应优先级判断。
    urgency: UrgencyLevel = Field(..., description="紧急度。")
    # 已选择的 Agent 列表，展示本轮排障规划将调用哪些角色。
    selected_agents: list[AgentType] = Field(default_factory=list, description="已选择的 Agent 列表。")
    # 已选择的工具列表，展示本轮排障规划将使用哪些工具能力。
    selected_tools: list[ToolType] = Field(default_factory=list, description="已选择的工具列表。")
    # 总结说明，明确当前阶段只返回骨架结果而非真实工具结论。
    summary: str = Field(..., description="总结说明。")
    # 已确认事实列表，保留当前可以直接公开给调用方的事实。
    confirmed_facts: list[ConfirmedFact] = Field(default_factory=list, description="已确认事实列表。")
    # 当前假设列表，帮助调用方理解后续调查方向。
    hypotheses: list[HypothesisRecord] = Field(default_factory=list, description="当前假设列表。")
    # 下一步建议列表，输出下一轮应做的排查动作。
    next_steps: list[str] = Field(default_factory=list, description="下一步建议列表。")
    # 待审批动作列表，承接 guarded 动作审批需求。
    pending_actions: list[ActionPlanRecord] = Field(default_factory=list, description="待审批动作列表。")
    # 是否已升级，供上层系统判断是否需要触发人工接管。
    escalated: bool = Field(..., description="是否已升级。")
    # 接口耗时，便于后续 Monitor 接入时复用。
    latency_ms: int = Field(..., ge=0, description="接口耗时（毫秒）。")


class ApproveActionRequest(BaseModel):
    """审批动作请求。"""

    # 允许模型稳定序列化，保持接口输出风格统一。
    model_config = ConfigDict(use_enum_values=True)

    # 会话唯一标识，用于找到需要审批的排障状态。
    session_id: str = Field(..., description="会话唯一标识。")
    # 动作唯一标识，用于精确定位待审批动作。
    action_id: str = Field(..., description="动作唯一标识。")
    # 审批结论，标记本次是批准还是拒绝。
    approved: bool = Field(..., description="审批结论。")
    # 审批人标识，用于记录审计链路。
    approver_id: str = Field(..., description="审批人标识。")
    # 审批备注，保留人工判断的上下文说明。
    note: str | None = Field(default=None, description="审批备注。")


class ApproveActionResponse(BaseModel):
    """审批动作响应。"""

    # 允许模型稳定序列化，保持接口输出风格统一。
    model_config = ConfigDict(use_enum_values=True)

    # 会话唯一标识，便于调用方确认更新的是哪个排障会话。
    session_id: str = Field(..., description="会话唯一标识。")
    # 动作唯一标识，回显本次处理的动作。
    action_id: str = Field(..., description="动作唯一标识。")
    # 审批结论，回显本次处理结果。
    approved: bool = Field(..., description="审批结论。")
    # 执行结果，当前阶段只返回模拟执行结果。
    execution_result: ExecutionResultRecord = Field(..., description="执行结果。")
    # 更新后的总结，说明状态如何变化。
    updated_summary: str = Field(..., description="更新后的总结。")
    # 更新后的状态，作为后续恢复图执行的核心载体。
    updated_state: InvestigationState = Field(..., description="更新后的状态。")
    # 审计记录，保留审批链路基础信息。
    audit_record: AuditRecord = Field(..., description="审计记录。")
