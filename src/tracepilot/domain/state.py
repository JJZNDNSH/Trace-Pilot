"""TracePilot 调查状态对象定义。"""

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
    """自研 Agent Loop 的统一排障状态对象。"""

    # 允许模型安全处理枚举值，保证接口层和编排层共用同一份状态对象。
    model_config = ConfigDict(use_enum_values=True)

    # 会话唯一标识，用于串联 investigate 和 approve 两类接口。
    session_id: str = Field(..., description="会话唯一标识。")
    # 用户标识，用于保留最基础的调用方上下文。
    user_id: str = Field(..., description="用户标识。")
    # 目标环境，用于标识当前故障发生在哪个环境。
    environment: str = Field(..., description="目标环境。")
    # 场景标识，用于对齐 mock 数据和标准场景。
    scenario_id: str | None = Field(default=None, description="场景标识。")
    # 原始故障描述，是整个编排的核心输入。
    problem_statement: str = Field(..., description="原始故障描述。")
    # 故障域分类，用于指导当前轮的调查规划。
    fault_type: FaultType = Field(..., description="故障域分类。")
    # 紧急度，用于表达当前故障的优先级。
    urgency: UrgencyLevel = Field(..., description="紧急度。")
    # 影响范围，用于表达当前故障影响的是单服务还是更大范围。
    impact_scope: ImpactScope = Field(..., description="影响范围。")
    # 已选择的 Agent 列表，用于保留当前轮的角色规划结果。
    selected_agents: list[AgentType] = Field(default_factory=list, description="已选择的 Agent 列表。")
    # 已选择的工具列表，用于保留当前轮准备执行的工具计划。
    selected_tools: list[ToolType] = Field(default_factory=list, description="已选择的工具列表。")
    # 已确认事实列表，用于累计跨步骤沉淀的稳定结论。
    confirmed_facts: list[ConfirmedFact] = Field(default_factory=list, description="已确认事实列表。")
    # 当前有效假设列表，用于保存仍待验证的排障方向。
    hypotheses: list[HypothesisRecord] = Field(default_factory=list, description="当前有效假设列表。")
    # 已否定假设列表，用于避免重复排查已经排除的方向。
    rejected_hypotheses: list[HypothesisRecord] = Field(default_factory=list, description="已否定假设列表。")
    # 证据摘要列表，用于保留请求、日志、指标等来源的结构化证据。
    evidence: list[EvidenceRecord] = Field(default_factory=list, description="证据摘要列表。")
    # 工具结果列表，用于记录每轮工具执行或占位执行结果。
    tool_results: list[ToolResultRecord] = Field(default_factory=list, description="工具结果列表。")
    # 当前轮调查发现，用于在 merge_findings 前暂存结构化发现。
    investigation_findings: list[dict[str, str]] = Field(default_factory=list, description="当前轮调查发现。")
    # 知识检索摘要，用于保留 retrieve_knowledge 的输出。
    knowledge_summary: str | None = Field(default=None, description="知识检索摘要。")
    # 阶段摘要列表，用于按节点记录状态压缩结果。
    stage_summaries: list[StageSummaryRecord] = Field(default_factory=list, description="阶段摘要列表。")
    # 当前阶段摘要，用于为最终响应和下一步决策提供最近一次压缩结果。
    stage_summary: str | None = Field(default=None, description="当前阶段摘要。")
    # 待补充问题列表，用于后续多轮交互扩展。
    pending_questions: list[PendingQuestionRecord] = Field(default_factory=list, description="待补充问题列表。")
    # 候选动作列表，用于保留尚未进入审批流的动作建议。
    candidate_actions: list[ActionPlanRecord] = Field(default_factory=list, description="候选动作列表。")
    # 待审批动作列表，用于承接 guarded 动作的审批输入。
    pending_actions: list[ActionPlanRecord] = Field(default_factory=list, description="待审批动作列表。")
    # 已批准动作列表，用于审批通过后恢复执行。
    approved_actions: list[ActionPlanRecord] = Field(default_factory=list, description="已批准动作列表。")
    # 交接摘要，用于后续人工接手场景的摘要输出。
    handoff_summary: str | None = Field(default=None, description="交接摘要。")
    # 是否已升级，用于表达当前故障是否进入更高优先级处理。
    escalated: bool = Field(default=False, description="是否已升级。")
    # 下一步建议列表，用于输出当前轮之后的建议动作。
    next_steps: list[str] = Field(default_factory=list, description="下一步建议列表。")
    # 主循环计数，用于限制 Agent Loop 的最大轮次。
    loop_count: int = Field(default=0, ge=0, description="主循环计数。")
    # 是否应该直接收口响应，用于控制 loop 或 generate_response 分支。
    should_respond: bool = Field(default=False, description="是否应该直接收口响应。")
    # 最终响应摘要，用于 generate_response 产出可直接返回的总结。
    response_summary: str | None = Field(default=None, description="最终响应摘要。")
    # 当前图节点，用于标识编排器停留在哪个步骤。
    current_node: InvestigationGraphNode = Field(..., description="当前图节点。")
    # 会话状态，用于标识当前处于调查中、待审批还是已完成。
    status: InvestigationStatus = Field(..., description="会话状态。")
