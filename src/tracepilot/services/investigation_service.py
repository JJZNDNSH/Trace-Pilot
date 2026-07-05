"""调查与审批服务骨架。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import HTTPException, status

from tracepilot.domain.enums import (
    ActionRiskLevel,
    AgentType,
    FaultType,
    ImpactScope,
    InvestigationGraphNode,
    InvestigationStatus,
    ToolExecutionStatus,
    ToolType,
    UrgencyLevel,
)
from tracepilot.domain.models import (
    ActionPlanRecord,
    AuditRecord,
    ConfirmedFact,
    EvidenceRecord,
    ExecutionResultRecord,
    HypothesisRecord,
    StageSummaryRecord,
    ToolResultRecord,
)
from tracepilot.domain.state import InvestigationState
from tracepilot.schemas.investigation import (
    ApproveActionRequest,
    ApproveActionResponse,
    InvestigateRequest,
    InvestigateResponse,
)


@dataclass
class InMemoryInvestigationStore:
    """排障状态的最小内存存储。"""

    # 使用 session_id 保存状态，满足当前阶段 investigate/approve 串联需求。
    states: dict[str, InvestigationState] = field(default_factory=dict)

    # 保存最新状态，保证审批接口能读取并更新同一会话。
    def save(self, state: InvestigationState) -> None:
        self.states[state.session_id] = state

    # 按会话读取状态，找不到时返回 None 交由服务层统一报错。
    def get(self, session_id: str) -> InvestigationState | None:
        return self.states.get(session_id)


class InvestigationService:
    """排障接口服务骨架。"""

    # 初始化服务并注入存储，便于测试时替换或隔离状态。
    def __init__(self, store: InMemoryInvestigationStore | None = None) -> None:
        self._store = store or InMemoryInvestigationStore()

    # 创建排障会话并返回第一阶段接口契约所需的固定结构。
    def investigate(self, request: InvestigateRequest) -> InvestigateResponse:
        started_at = perf_counter()

        # 先做轻量关键词分类，给 Phase 1 提供稳定的占位路由结果。
        fault_type = self._classify_fault_type(request.problem_statement)
        # 紧急度沿用相同思路占位，后续模块可直接替换为真实分类节点。
        urgency = self._classify_urgency(request.problem_statement)
        # 影响范围先按用户面与跨服务关键词做静态判断，避免接口层后续重做。
        impact_scope = self._classify_impact_scope(request.problem_statement)
        # Agent 选择只给出骨架规划，不触发真实 Agent 执行。
        selected_agents = self._select_agents(fault_type)
        # 工具选择只给出契约占位，不做真实工具调用。
        selected_tools = self._select_tools(fault_type)
        # 待审批动作只在明显需要 guarded 动作的场景里返回示例结构。
        pending_actions = self._build_pending_actions(fault_type)
        # 已确认事实先沉淀输入侧可直接确认的信息，保证响应结构稳定。
        confirmed_facts = self._build_confirmed_facts(request)
        # 初始假设为后续多 Agent 和知识检索保留扩展位。
        hypotheses = self._build_hypotheses(fault_type)

        state = InvestigationState(
            session_id=str(uuid4()),
            user_id=request.user_id,
            environment=request.environment,
            scenario_id=request.scenario_id,
            problem_statement=request.problem_statement,
            fault_type=fault_type,
            urgency=urgency,
            impact_scope=impact_scope,
            selected_agents=selected_agents,
            selected_tools=selected_tools,
            confirmed_facts=confirmed_facts,
            hypotheses=hypotheses,
            rejected_hypotheses=[],
            evidence=self._build_evidence(request.problem_statement),
            tool_results=self._build_tool_results(selected_tools),
            stage_summaries=self._build_stage_summaries(fault_type),
            pending_questions=[],
            candidate_actions=pending_actions.copy(),
            pending_actions=pending_actions,
            approved_actions=[],
            handoff_summary=None,
            escalated=urgency == UrgencyLevel.CRITICAL,
            current_node=(
                InvestigationGraphNode.AWAIT_APPROVAL
                if pending_actions
                else InvestigationGraphNode.GENERATE_RESPONSE
            ),
            status=(
                InvestigationStatus.AWAITING_APPROVAL
                if pending_actions
                else InvestigationStatus.IN_PROGRESS
            ),
        )
        self._store.save(state)

        latency_ms = int((perf_counter() - started_at) * 1000)
        return InvestigateResponse(
            session_id=state.session_id,
            fault_type=state.fault_type,
            urgency=state.urgency,
            selected_agents=state.selected_agents,
            selected_tools=state.selected_tools,
            summary=(
                "已创建排障会话并返回接口骨架结果，当前阶段仅完成领域建模、状态初始化和审批占位。"
            ),
            confirmed_facts=state.confirmed_facts,
            hypotheses=state.hypotheses,
            next_steps=self._build_next_steps(state),
            pending_actions=state.pending_actions,
            escalated=state.escalated,
            latency_ms=latency_ms,
        )

    # 处理动作审批，并通过内存状态模拟审批后的图恢复入口。
    def approve_action(self, request: ApproveActionRequest) -> ApproveActionResponse:
        state = self._store.get(request.session_id)
        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{request.session_id}' not found.",
            )

        # 只允许审批当前待审批列表中的动作，避免越权更新无关状态。
        action = next((item for item in state.pending_actions if item.action_id == request.action_id), None)
        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pending action '{request.action_id}' not found.",
            )

        # 审批后先从待审批列表移除，保持状态只反映当前未决动作。
        remaining_actions = [item for item in state.pending_actions if item.action_id != request.action_id]
        state.pending_actions = remaining_actions

        if request.approved:
            # 批准后把动作转入已批准列表，为后续 execute_actions 节点预留输入。
            state.approved_actions.append(action)
            state.current_node = InvestigationGraphNode.EXECUTE_ACTIONS
            state.status = InvestigationStatus.IN_PROGRESS
            execution_result = ExecutionResultRecord(
                status="simulated",
                message="动作已通过审批，当前阶段仅记录模拟执行结果，未调用真实工具。",
                simulated=True,
            )
            updated_summary = "待审批动作已批准，状态已切换到 execute_actions 占位节点。"
        else:
            # 拒绝后直接回到响应生成节点，避免骨架流程停留在不可执行状态。
            state.current_node = InvestigationGraphNode.GENERATE_RESPONSE
            state.status = InvestigationStatus.COMPLETED
            execution_result = ExecutionResultRecord(
                status="skipped",
                message="动作未获批准，系统保留审批结果并结束本次模拟执行。",
                simulated=True,
            )
            updated_summary = "待审批动作已拒绝，状态已回到 generate_response 占位节点。"

        # 根据剩余待审批动作同步会话状态，保证多动作场景下状态可继续扩展。
        if state.pending_actions:
            state.current_node = InvestigationGraphNode.AWAIT_APPROVAL
            state.status = InvestigationStatus.AWAITING_APPROVAL

        audit_record = AuditRecord(
            approver_id=request.approver_id,
            approved=request.approved,
            note=request.note,
            recorded_at=self._utc_now(),
        )
        self._store.save(state)

        return ApproveActionResponse(
            session_id=state.session_id,
            action_id=request.action_id,
            approved=request.approved,
            execution_result=execution_result,
            updated_summary=updated_summary,
            updated_state=state,
            audit_record=audit_record,
        )

    # 根据故障描述做最小分类，确保接口层字段在后续模块中无需重做。
    def _classify_fault_type(self, problem_statement: str) -> FaultType:
        text = problem_statement.lower()
        if any(keyword in text for keyword in ["release", "rollback", "deploy", "发布", "回滚"]):
            return FaultType.RELEASE_REGRESSION
        if any(keyword in text for keyword in ["dependency", "下游", "依赖", "third-party"]):
            return FaultType.DEPENDENCY_FAILURE
        if any(keyword in text for keyword in ["gc", "jvm", "full gc"]):
            return FaultType.JVM_GC
        if any(keyword in text for keyword in ["cpu", "memory", "saturation", "db", "数据库"]):
            return FaultType.RESOURCE_SATURATION
        if any(keyword in text for keyword in ["false alarm", "误报"]):
            return FaultType.FALSE_ALARM
        if any(keyword in text for keyword in ["500", "401", "timeout", "api", "接口"]):
            return FaultType.API_ERROR
        return FaultType.UNKNOWN

    # 根据输入关键词推断紧急度，为后续真正的分级节点保留稳定输出位。
    def _classify_urgency(self, problem_statement: str) -> UrgencyLevel:
        text = problem_statement.lower()
        if any(keyword in text for keyword in ["critical", "sev1", "全站", "大面积", "major"]):
            return UrgencyLevel.CRITICAL
        if any(keyword in text for keyword in ["500", "timeout", "latency", "error", "告警"]):
            return UrgencyLevel.HIGH
        if any(keyword in text for keyword in ["warning", "抖动", "波动"]):
            return UrgencyLevel.MEDIUM
        return UrgencyLevel.LOW

    # 根据故障描述推断影响范围，先为升级和审批边界提供静态占位。
    def _classify_impact_scope(self, problem_statement: str) -> ImpactScope:
        text = problem_statement.lower()
        if any(keyword in text for keyword in ["用户", "customer", "订单", "支付", "login", "登录"]):
            return ImpactScope.USER_FACING
        if any(keyword in text for keyword in ["dependency", "依赖", "下游", "跨服务"]):
            return ImpactScope.CROSS_SERVICE
        if problem_statement.strip():
            return ImpactScope.SINGLE_SERVICE
        return ImpactScope.UNKNOWN

    # 按故障域选择最小 Agent 集合，让前后端先围绕稳定契约开发。
    def _select_agents(self, fault_type: FaultType) -> list[AgentType]:
        if fault_type == FaultType.RELEASE_REGRESSION:
            return [AgentType.TRIAGE, AgentType.CHANGE, AgentType.LOGS]
        if fault_type == FaultType.DEPENDENCY_FAILURE:
            return [AgentType.TRIAGE, AgentType.DEPENDENCY, AgentType.METRICS]
        if fault_type == FaultType.JVM_GC:
            return [AgentType.TRIAGE, AgentType.METRICS, AgentType.LOGS]
        if fault_type == FaultType.RESOURCE_SATURATION:
            return [AgentType.TRIAGE, AgentType.METRICS]
        return [AgentType.TRIAGE, AgentType.LOGS]

    # 按故障域选择最小工具集合，只输出规划结果不执行真实工具。
    def _select_tools(self, fault_type: FaultType) -> list[ToolType]:
        if fault_type == FaultType.RELEASE_REGRESSION:
            return [ToolType.CHANGE_QUERY, ToolType.LOG_QUERY, ToolType.RUNBOOK_LOOKUP]
        if fault_type == FaultType.DEPENDENCY_FAILURE:
            return [ToolType.DEPENDENCY_QUERY, ToolType.METRICS_QUERY, ToolType.RUNBOOK_LOOKUP]
        if fault_type == FaultType.JVM_GC:
            return [ToolType.METRICS_QUERY, ToolType.LOG_QUERY, ToolType.RUNBOOK_LOOKUP]
        if fault_type == FaultType.RESOURCE_SATURATION:
            return [ToolType.METRICS_QUERY, ToolType.HEALTH_CHECK_RETRY]
        return [ToolType.LOG_QUERY, ToolType.RUNBOOK_LOOKUP]

    # 仅在需要审批的风险动作场景里返回占位动作，验证审批接口契约。
    def _build_pending_actions(self, fault_type: FaultType) -> list[ActionPlanRecord]:
        if fault_type != FaultType.RELEASE_REGRESSION:
            return []
        return [
            ActionPlanRecord(
                action_id=f"act-{uuid4().hex[:8]}",
                title="回滚最近一次发布",
                description="建议回滚最近一次生产发布，以快速验证错误率上升是否由变更引起。",
                risk_level=ActionRiskLevel.GUARDED,
                target="production.release",
                reason="故障描述命中发布回归特征，需要人工确认后再进入执行环节。",
                requires_approval=True,
            )
        ]

    # 生成可直接确认的基础事实，确保接口响应即使在骨架阶段也结构完整。
    def _build_confirmed_facts(self, request: InvestigateRequest) -> list[ConfirmedFact]:
        return [
            ConfirmedFact(
                fact_id=f"fact-{uuid4().hex[:8]}",
                statement=f"收到来自 {request.environment} 环境的排障请求。",
                source="request",
            ),
            ConfirmedFact(
                fact_id=f"fact-{uuid4().hex[:8]}",
                statement=f"原始故障描述为：{request.problem_statement}",
                source="request",
            ),
        ]

    # 生成初始假设，为后续真实 Agent 和知识检索接管时保留统一结构。
    def _build_hypotheses(self, fault_type: FaultType) -> list[HypothesisRecord]:
        mapping = {
            FaultType.RELEASE_REGRESSION: "最近一次发布可能引入了接口行为回归。",
            FaultType.DEPENDENCY_FAILURE: "下游依赖异常可能导致上游调用超时或失败。",
            FaultType.JVM_GC: "JVM Full GC 可能造成请求延迟抖动。",
            FaultType.RESOURCE_SATURATION: "资源饱和可能导致吞吐下降或错误率上升。",
            FaultType.API_ERROR: "接口侧错误可能与流量、配置或依赖变化相关。",
            FaultType.FALSE_ALARM: "当前告警可能不代表真实用户影响。",
            FaultType.UNKNOWN: "需要更多上下文才能定位首要排查方向。",
        }
        return [
            HypothesisRecord(
                hypothesis_id=f"hyp-{uuid4().hex[:8]}",
                statement=mapping[fault_type],
                confidence=0.55,
                supporting_evidence_ids=[],
            )
        ]

    # 构建证据摘要占位，保证状态对象字段在后续模块无需改名或重塑。
    def _build_evidence(self, problem_statement: str) -> list[EvidenceRecord]:
        return [
            EvidenceRecord(
                evidence_id=f"ev-{uuid4().hex[:8]}",
                source_type="request",
                summary="当前阶段仅持有用户输入描述，尚未采集外部系统证据。",
                detail=problem_statement,
                tool_name=None,
            )
        ]

    # 构建工具结果占位，明确当前仅做规划未执行真实工具。
    def _build_tool_results(self, selected_tools: list[ToolType]) -> list[ToolResultRecord]:
        return [
            ToolResultRecord(
                tool=tool,
                status=ToolExecutionStatus.SKIPPED,
                summary="Phase 1 仅建立工具选择契约，未执行真实工具。",
                error_message=None,
            )
            for tool in selected_tools
        ]

    # 构建阶段摘要占位，让状态对象从第一阶段就具备压缩入口。
    def _build_stage_summaries(self, fault_type: FaultType) -> list[StageSummaryRecord]:
        now = self._utc_now()
        return [
            StageSummaryRecord(
                stage=InvestigationGraphNode.CLASSIFY_INCIDENT.value,
                summary=f"已完成初步故障分类：{fault_type.value}。",
                updated_at=now,
            ),
            StageSummaryRecord(
                stage=InvestigationGraphNode.PREPARE_ACTIONS.value,
                summary="已完成动作规划占位，但尚未进入真实执行阶段。",
                updated_at=now,
            ),
        ]

    # 输出下一步建议，帮助接口消费者理解后续模块将如何接管。
    def _build_next_steps(self, state: InvestigationState) -> list[str]:
        steps = [
            "进入 load_context 节点补充场景和历史上下文。",
            "进入 retrieve_knowledge 节点补充 Runbook / 复盘 / 依赖知识。",
            "进入 plan_investigation 节点生成下一轮工具计划。",
        ]
        if state.pending_actions:
            steps.append("当前存在 guarded 动作，请先调用 /actions/approve 完成审批。")
        return steps

    # 统一生成 UTC 时间字符串，避免不同模型各自处理时间格式。
    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()
