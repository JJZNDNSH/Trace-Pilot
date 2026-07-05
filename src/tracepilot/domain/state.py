"""TracePilot LangGraph 核心状态对象。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from tracepilot.domain.enums import (
    AgentType,
    FaultType,
    ImpactScope,
    InvestigationGraphNode,
    InvestigationStatus,
    ToolType,
    UrgencyLevel,
)
from tracepilot.domain.models import (
    ActionPlanRecord,
    ConfirmedFact,
    EvidenceRecord,
    HypothesisRecord,
    PendingQuestionRecord,
    StageSummaryRecord,
    ToolResultRecord,
)


class InvestigationState(BaseModel):
    """LangGraph 主状态对象骨架。"""

    # 允许模型从枚举等对象安全构造，便于在路由和服务间直接传递状态对象。
    model_config = ConfigDict(use_enum_values=True)

    # 会话唯一标识，用于串联 investigate 和 approve 两类接口。
    session_id: str = Field(..., description="会话唯一标识。")
    # 用户标识，便于后续扩展用户画像和权限治理。
    user_id: str = Field(..., description="用户标识。")
    # 目标环境，标记当前排障所处的环境上下文。
    environment: str = Field(..., description="目标环境。")
    # 场景标识，便于评测或 mock 数据对齐。
    scenario_id: str | None = Field(default=None, description="场景标识。")
    # 原始故障描述，是整条排障链路的输入基线。
    problem_statement: str = Field(..., description="原始故障描述。")
    # 故障域分类，作为主图路由的基础决策输入。
    fault_type: FaultType = Field(..., description="故障域分类。")
    # 紧急度，用于控制升级与响应优先级。
    urgency: UrgencyLevel = Field(..., description="紧急度。")
    # 影响范围，用于后续升级和动作风险判断。
    impact_scope: ImpactScope = Field(..., description="影响范围。")
    # 已选择的 Agent 列表，描述当前主图计划使用哪些分析角色。
    selected_agents: list[AgentType] = Field(default_factory=list, description="已选择的 Agent 列表。")
    # 已选择的工具列表，描述当前阶段计划使用哪些工具能力。
    selected_tools: list[ToolType] = Field(default_factory=list, description="已选择的工具列表。")
    # 已确认事实列表，保留能够支撑结论的稳定事实。
    confirmed_facts: list[ConfirmedFact] = Field(default_factory=list, description="已确认事实列表。")
    # 当前有效假设列表，保留仍需要继续验证的方向。
    hypotheses: list[HypothesisRecord] = Field(default_factory=list, description="当前有效假设列表。")
    # 已否定假设列表，避免后续重复排查已排除方向。
    rejected_hypotheses: list[HypothesisRecord] = Field(default_factory=list, description="已否定假设列表。")
    # 证据摘要列表，沉淀日志、指标、变更等结构化证据。
    evidence: list[EvidenceRecord] = Field(default_factory=list, description="证据摘要列表。")
    # 工具结果列表，记录当前阶段的工具执行输出。
    tool_results: list[ToolResultRecord] = Field(default_factory=list, description="工具结果列表。")
    # 阶段摘要列表，用于后续状态压缩和 handoff 摘要。
    stage_summaries: list[StageSummaryRecord] = Field(default_factory=list, description="阶段摘要列表。")
    # 待补充问题列表，用于后续多轮交互时追问缺失信息。
    pending_questions: list[PendingQuestionRecord] = Field(default_factory=list, description="待补充问题列表。")
    # 候选动作列表，保留尚未进入审批的潜在动作建议。
    candidate_actions: list[ActionPlanRecord] = Field(default_factory=list, description="候选动作列表。")
    # 待审批动作列表，承接 guarded 动作的审批前状态。
    pending_actions: list[ActionPlanRecord] = Field(default_factory=list, description="待审批动作列表。")
    # 已批准动作列表，便于后续恢复执行或生成 handoff。
    approved_actions: list[ActionPlanRecord] = Field(default_factory=list, description="已批准动作列表。")
    # 交接摘要，供超出自动处理边界时输出给人工接手者。
    handoff_summary: str | None = Field(default=None, description="交接摘要。")
    # 是否已升级，标记是否需要进入更高等级协同流程。
    escalated: bool = Field(default=False, description="是否已升级。")
    # 当前图节点，提供后续 LangGraph 恢复执行所需的锚点。
    current_node: InvestigationGraphNode = Field(..., description="当前图节点。")
    # 会话状态，明确是进行中、待审批还是已完成。
    status: InvestigationStatus = Field(..., description="会话状态。")
