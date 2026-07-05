"""TracePilot 领域值对象定义。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from tracepilot.domain.enums import ActionRiskLevel, ToolExecutionStatus, ToolType


class ConfirmedFact(BaseModel):
    """已确认事实。"""

    # 允许模型从枚举等对象安全构造，便于后续状态回写复用同一模型。
    model_config = ConfigDict(use_enum_values=True)

    # 事实唯一标识，便于后续多轮排障时稳定引用。
    fact_id: str = Field(..., description="事实唯一标识。")
    # 事实内容，描述当前已确认的结论。
    statement: str = Field(..., description="事实内容。")
    # 事实来源，标记该事实由哪类证据得出。
    source: str = Field(..., description="事实来源。")


class HypothesisRecord(BaseModel):
    """排障假设。"""

    # 允许模型从枚举等对象安全构造，便于后续状态回写复用同一模型。
    model_config = ConfigDict(use_enum_values=True)

    # 假设唯一标识，便于在确认或否定时精确引用。
    hypothesis_id: str = Field(..., description="假设唯一标识。")
    # 假设内容，描述当前怀疑的故障原因。
    statement: str = Field(..., description="假设内容。")
    # 置信度，保留后续排序和压缩状态所需的基础分值。
    confidence: float = Field(..., ge=0.0, le=1.0, description="假设置信度。")
    # 关联证据列表，便于后续 Agent 合并时建立因果链。
    supporting_evidence_ids: list[str] = Field(default_factory=list, description="关联证据标识列表。")


class EvidenceRecord(BaseModel):
    """证据摘要。"""

    # 允许模型从枚举等对象安全构造，便于后续状态回写复用同一模型。
    model_config = ConfigDict(use_enum_values=True)

    # 证据唯一标识，便于后续压缩和引用。
    evidence_id: str = Field(..., description="证据唯一标识。")
    # 证据来源类型，区分日志、指标、变更等来源。
    source_type: str = Field(..., description="证据来源类型。")
    # 证据摘要，返回给接口消费者的核心内容。
    summary: str = Field(..., description="证据摘要。")
    # 证据明细，保留结构化扩展位但当前阶段不接真实工具。
    detail: str | None = Field(default=None, description="证据明细。")
    # 产生证据的工具名，便于后续做工具治理统计。
    tool_name: ToolType | None = Field(default=None, description="产生证据的工具名。")


class ToolResultRecord(BaseModel):
    """工具调用结果摘要。"""

    # 允许模型从枚举等对象安全构造，便于后续状态回写复用同一模型。
    model_config = ConfigDict(use_enum_values=True)

    # 工具名称，标记是哪一个工具产生了本条结果。
    tool: ToolType = Field(..., description="工具名称。")
    # 工具状态，区分成功、失败或跳过。
    status: ToolExecutionStatus = Field(..., description="工具状态。")
    # 结果摘要，保留用户可读的执行反馈。
    summary: str = Field(..., description="结果摘要。")
    # 错误信息，只有失败时才填充，方便后续失败证据沉淀。
    error_message: str | None = Field(default=None, description="错误信息。")


class StageSummaryRecord(BaseModel):
    """阶段摘要。"""

    # 允许模型从枚举等对象安全构造，便于后续状态回写复用同一模型。
    model_config = ConfigDict(use_enum_values=True)

    # 阶段名称，和主图节点保持一致，便于追踪状态演进。
    stage: str = Field(..., description="阶段名称。")
    # 阶段总结，浓缩该阶段的核心产出。
    summary: str = Field(..., description="阶段总结。")
    # 更新时间，便于后续 handoff 摘要生成时间线。
    updated_at: str = Field(..., description="更新时间。")


class PendingQuestionRecord(BaseModel):
    """待补充问题。"""

    # 允许模型从枚举等对象安全构造，便于后续状态回写复用同一模型。
    model_config = ConfigDict(use_enum_values=True)

    # 问题唯一标识，便于用户回复时和状态关联。
    question_id: str = Field(..., description="问题唯一标识。")
    # 问题内容，提示用户补充必要上下文。
    question: str = Field(..., description="问题内容。")
    # 提问原因，说明为什么需要该补充信息。
    reason: str = Field(..., description="提问原因。")


class ActionPlanRecord(BaseModel):
    """候选或待审批动作。"""

    # 允许模型从枚举等对象安全构造，便于后续状态回写复用同一模型。
    model_config = ConfigDict(use_enum_values=True)

    # 动作唯一标识，便于审批接口精确引用。
    action_id: str = Field(..., description="动作唯一标识。")
    # 动作标题，便于在审批面板快速识别。
    title: str = Field(..., description="动作标题。")
    # 动作说明，解释准备执行什么动作。
    description: str = Field(..., description="动作说明。")
    # 风险等级，直接对应 auto / guarded / denied 治理规则。
    risk_level: ActionRiskLevel = Field(..., description="风险等级。")
    # 动作目标，标记将作用到的服务或资源。
    target: str = Field(..., description="动作目标。")
    # 动作原因，说明为什么当前建议该动作。
    reason: str = Field(..., description="动作原因。")
    # 是否需要审批，便于前端和 CLI 做统一渲染。
    requires_approval: bool = Field(..., description="是否需要审批。")


class ExecutionResultRecord(BaseModel):
    """动作执行结果。"""

    # 允许模型从枚举等对象安全构造，便于后续状态回写复用同一模型。
    model_config = ConfigDict(use_enum_values=True)

    # 执行状态，当前阶段只返回 simulated 或 skipped 等占位值。
    status: str = Field(..., description="执行状态。")
    # 结果说明，解释动作是否被模拟执行。
    message: str = Field(..., description="结果说明。")
    # 是否为模拟执行，明确当前阶段未接真实执行工具。
    simulated: bool = Field(..., description="是否为模拟执行。")


class AuditRecord(BaseModel):
    """审批审计记录。"""

    # 允许模型从枚举等对象安全构造，便于后续状态回写复用同一模型。
    model_config = ConfigDict(use_enum_values=True)

    # 审批人标识，满足后续审计追溯需求。
    approver_id: str = Field(..., description="审批人标识。")
    # 审批结论，记录本次是批准还是拒绝。
    approved: bool = Field(..., description="审批结论。")
    # 审批备注，保留人工决策说明。
    note: str | None = Field(default=None, description="审批备注。")
    # 记录时间，便于生成审计时间线。
    recorded_at: str = Field(..., description="记录时间。")
