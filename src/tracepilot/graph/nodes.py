"""TracePilot 自研 Agent Loop 步骤节点定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from tracepilot.adapters import (
    AlertAdapter,
    ChangeAdapter,
    CMDBAdapter,
    LogAdapter,
    MetricsAdapter,
    MockAlertAdapter,
    MockChangeAdapter,
    MockCMDBAdapter,
    MockLogAdapter,
    MockMetricsAdapter,
    MockRunbookAdapter,
    MockTicketAdapter,
    RunbookAdapter,
    ScenarioDataError,
    TicketAdapter,
)
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
    ConfirmedFact,
    EvidenceRecord,
    HypothesisRecord,
    StageSummaryRecord,
    ToolResultRecord,
)
from tracepilot.domain.state import InvestigationState
from tracepilot.schemas.investigation import InvestigateRequest

DEFAULT_MAX_LOOP_COUNT = 2


@dataclass(slots=True)
class InvestigationGraphDependencies:
    """自研编排器依赖集合。"""

    # 告警 adapter，用于初始化阶段补充基础监控上下文。
    alert_adapter: AlertAdapter = field(default_factory=MockAlertAdapter)
    # 日志 adapter，用于统一占位调查步骤读取日志证据。
    log_adapter: LogAdapter = field(default_factory=MockLogAdapter)
    # 指标 adapter，用于统一占位调查步骤读取指标证据。
    metrics_adapter: MetricsAdapter = field(default_factory=MockMetricsAdapter)
    # 变更 adapter，用于发布相关场景的占位调查。
    change_adapter: ChangeAdapter = field(default_factory=MockChangeAdapter)
    # 工单 adapter，用于知识检索阶段读取历史排障记录。
    ticket_adapter: TicketAdapter = field(default_factory=MockTicketAdapter)
    # Runbook adapter，用于知识检索阶段读取排障手册。
    runbook_adapter: RunbookAdapter = field(default_factory=MockRunbookAdapter)
    # CMDB adapter，用于初始化和依赖调查阶段读取服务元数据。
    cmdb_adapter: CMDBAdapter = field(default_factory=MockCMDBAdapter)
    # 最大循环次数，用于防止 Agent Loop 死循环。
    max_loop_count: int = DEFAULT_MAX_LOOP_COUNT


class InvestigationGraphNodes:
    """自研 Agent Loop 的步骤节点集合。"""

    # 初始化节点集合并注入 mock adapter 依赖，保证步骤逻辑可独立测试。
    def __init__(self, dependencies: InvestigationGraphDependencies | None = None) -> None:
        self._dependencies = dependencies or InvestigationGraphDependencies()

    # 构建编排器初始状态，保证所有后续步骤都从统一状态对象读取和写回。
    def build_initial_state(self, request: InvestigateRequest) -> InvestigationState:
        return InvestigationState(
            session_id=str(uuid4()),
            user_id=request.user_id,
            environment=request.environment,
            scenario_id=request.scenario_id,
            problem_statement=request.problem_statement,
            fault_type=FaultType.UNKNOWN,
            urgency=UrgencyLevel.LOW,
            impact_scope=ImpactScope.UNKNOWN,
            selected_agents=[],
            selected_tools=[],
            confirmed_facts=[],
            hypotheses=[],
            rejected_hypotheses=[],
            evidence=[],
            tool_results=[],
            investigation_findings=[],
            knowledge_summary=None,
            stage_summaries=[],
            stage_summary=None,
            pending_questions=[],
            candidate_actions=[],
            pending_actions=[],
            approved_actions=[],
            handoff_summary=None,
            escalated=False,
            next_steps=[],
            loop_count=0,
            should_respond=False,
            response_summary=None,
            current_node=InvestigationGraphNode.LOAD_CONTEXT,
            status=InvestigationStatus.IN_PROGRESS,
        )

    # 读取基础上下文并初始化默认事实，保证后续步骤拥有最小可用调查输入。
    # 读取：session_id、environment、problem_statement、scenario_id
    # 写入：confirmed_facts、evidence、stage_summary、next_steps、current_node、loop_count
    def load_context(self, state: InvestigationState) -> InvestigationState:
        state.loop_count = 0

        # 先沉淀请求侧的确定信息，保证没有外部数据时也能继续排障。
        state.confirmed_facts.extend(
            [
                ConfirmedFact(
                    fact_id=self._new_fact_id(),
                    statement=f"收到来自 {state.environment} 环境的排障请求。",
                    source="request",
                ),
                ConfirmedFact(
                    fact_id=self._new_fact_id(),
                    statement=f"原始故障描述为：{state.problem_statement}",
                    source="request",
                ),
            ]
        )
        state.evidence.append(
            EvidenceRecord(
                evidence_id=self._new_evidence_id(),
                source_type="request",
                summary="已记录用户提交的原始故障描述，作为初始化调查输入。",
                detail=state.problem_statement,
                tool_name=None,
            )
        )

        # 如果命中了标准场景，就额外补充告警和服务上下文，作为后续调查的基础底座。
        if state.scenario_id:
            alerts = self._safe_list_alerts(state.scenario_id)
            if alerts:
                state.confirmed_facts.append(
                    ConfirmedFact(
                        fact_id=self._new_fact_id(),
                        statement=f"标准场景包含 {len(alerts)} 条告警记录。",
                        source="alerts",
                    )
                )
            cmdb_record = self._safe_get_service(state.scenario_id)
            if cmdb_record is not None:
                state.confirmed_facts.append(
                    ConfirmedFact(
                        fact_id=self._new_fact_id(),
                        statement=f"目标服务归属团队为 {cmdb_record.owner_team}。",
                        source="cmdb",
                    )
                )

        summary = "已加载基础上下文，并完成排障状态默认值初始化。"
        self._append_stage_summary(state, InvestigationGraphNode.LOAD_CONTEXT.value, summary)
        state.next_steps = ["进入 classify_incident 完成初始分类。"]
        state.current_node = InvestigationGraphNode.CLASSIFY_INCIDENT
        return state

    # 对故障做初始分类，保证主循环开始前已经具备故障域和优先级判断。
    # 读取：problem_statement
    # 写入：fault_type、urgency、impact_scope、selected_agents、escalated、stage_summary、current_node
    def classify_incident(self, state: InvestigationState) -> InvestigationState:
        state.fault_type = self._classify_fault_type(state.problem_statement)
        state.urgency = self._classify_urgency(state.problem_statement)
        state.impact_scope = self._classify_impact_scope(state.problem_statement)
        state.selected_agents = self._select_agents(state.fault_type)
        state.escalated = state.urgency == UrgencyLevel.CRITICAL

        summary = (
            f"已完成故障初判：fault_type={state.fault_type.value}，"
            f"urgency={state.urgency.value}，impact_scope={state.impact_scope.value}。"
        )
        self._append_stage_summary(state, InvestigationGraphNode.CLASSIFY_INCIDENT.value, summary)
        state.next_steps = ["进入 retrieve_knowledge 补充 Runbook 和历史工单知识。"]
        state.current_node = InvestigationGraphNode.RETRIEVE_KNOWLEDGE
        return state

    # 检索知识摘要并写回状态，保证主循环在执行前就具备最小知识上下文。
    # 读取：scenario_id、fault_type
    # 写入：knowledge_summary、confirmed_facts、stage_summary、next_steps、current_node
    def retrieve_knowledge(self, state: InvestigationState) -> InvestigationState:
        summary_parts: list[str] = [f"故障域：{state.fault_type.value}。"]

        if state.scenario_id:
            runbook = self._safe_get_runbook(state.scenario_id)
            if runbook is not None:
                summary_parts.append(f"Runbook：{runbook.title}。")
                state.confirmed_facts.append(
                    ConfirmedFact(
                        fact_id=self._new_fact_id(),
                        statement=f"已检索到场景 Runbook《{runbook.title}》。",
                        source="runbook",
                    )
                )
            tickets = self._safe_list_tickets(state.scenario_id)
            if tickets:
                summary_parts.append(f"历史工单 {len(tickets)} 条。")
                state.confirmed_facts.append(
                    ConfirmedFact(
                        fact_id=self._new_fact_id(),
                        statement=f"历史工单中存在 {len(tickets)} 条同场景记录可供参考。",
                        source="tickets",
                    )
                )
        else:
            summary_parts.append("未提供标准场景，当前使用通用知识占位摘要。")

        state.knowledge_summary = "".join(summary_parts)
        self._append_stage_summary(
            state,
            InvestigationGraphNode.RETRIEVE_KNOWLEDGE.value,
            state.knowledge_summary,
        )
        state.next_steps = ["进入 Agent Loop，先执行 plan_investigation。"]
        state.current_node = InvestigationGraphNode.PLAN_INVESTIGATION
        return state

    # 规划当前轮调查动作，保证每轮 loop 都明确选用哪些工具和下一步重点。
    # 读取：fault_type、knowledge_summary、loop_count
    # 写入：selected_tools、next_steps、stage_summary、current_node
    def plan_investigation(self, state: InvestigationState) -> InvestigationState:
        state.selected_tools = self._select_tools(state.fault_type)

        # 每轮都显式刷新 next_steps，保证外部能看到当前轮计划而不是旧值。
        state.next_steps = [
            f"执行第 {state.loop_count + 1} 轮占位调查。",
            f"优先围绕 {', '.join(tool.value for tool in state.selected_tools)} 收集证据。",
        ]
        if state.knowledge_summary:
            state.next_steps.append(f"参考知识摘要：{state.knowledge_summary}")

        summary = (
            f"第 {state.loop_count + 1} 轮计划已生成，"
            f"将使用 {', '.join(tool.value for tool in state.selected_tools)}。"
        )
        self._append_stage_summary(state, InvestigationGraphNode.PLAN_INVESTIGATION.value, summary)
        state.current_node = InvestigationGraphNode.RUN_INVESTIGATION_STEP
        return state

    # 执行统一占位调查步骤，保证本模块先具备“可循环的执行点”而不是单次直线流程。
    # 读取：scenario_id、selected_tools、fault_type、loop_count
    # 写入：investigation_findings、tool_results、stage_summary、current_node
    def run_investigation_step(self, state: InvestigationState) -> InvestigationState:
        findings: list[dict[str, str]] = []

        # 当前模块统一把多种工具调查压缩到一个执行点里，后续模块 5 再拆成多 Agent 步骤。
        for tool in state.selected_tools:
            summary = self._build_finding_for_tool(state, tool)
            findings.append({"tool": tool.value, "summary": summary})
            state.tool_results.append(
                ToolResultRecord(
                    tool=tool,
                    status=ToolExecutionStatus.SUCCESS,
                    summary=summary,
                    error_message=None,
                )
            )

        state.investigation_findings = findings
        summary = f"已完成第 {state.loop_count + 1} 轮统一占位调查，共产出 {len(findings)} 条 findings。"
        self._append_stage_summary(state, InvestigationGraphNode.RUN_INVESTIGATION_STEP.value, summary)
        state.current_node = InvestigationGraphNode.MERGE_FINDINGS
        return state

    # 合并本轮 findings，保证调查结果能沉淀为稳定事实、假设和动作建议。
    # 读取：investigation_findings、fault_type
    # 写入：confirmed_facts、hypotheses、candidate_actions、pending_actions、next_steps、stage_summary、current_node
    def merge_findings(self, state: InvestigationState) -> InvestigationState:
        seen_statements = {fact.statement for fact in state.confirmed_facts}

        # 将结构化 findings 沉淀为事实，保证后续压缩和决策都基于统一数据结构。
        for finding in state.investigation_findings:
            statement = finding["summary"]
            if statement in seen_statements:
                continue
            state.confirmed_facts.append(
                ConfirmedFact(
                    fact_id=self._new_fact_id(),
                    statement=statement,
                    source=finding["tool"],
                )
            )
            state.evidence.append(
                EvidenceRecord(
                    evidence_id=self._new_evidence_id(),
                    source_type=finding["tool"],
                    summary=statement,
                    detail=None,
                    tool_name=ToolType(finding["tool"]),
                )
            )
            seen_statements.add(statement)

        hypothesis = self._build_hypothesis_from_findings(state)
        if hypothesis is not None:
            state.hypotheses = [hypothesis]

        # 先保留 guarded 动作建议占位，后续审批流模块直接从这里挂接。
        if not state.pending_actions:
            pending_actions = self._build_pending_actions(state.fault_type)
            state.candidate_actions = pending_actions.copy()
            state.pending_actions = pending_actions

        state.next_steps = ["进入 compress_state 生成阶段摘要。"]
        summary = f"已合并 {len(state.investigation_findings)} 条 findings 到主状态。"
        self._append_stage_summary(state, InvestigationGraphNode.MERGE_FINDINGS.value, summary)
        state.current_node = InvestigationGraphNode.COMPRESS_STATE
        return state

    # 压缩当前轮状态，保证长上下文在 loop 中能够持续收敛为结构化摘要。
    # 读取：confirmed_facts、hypotheses、loop_count
    # 写入：stage_summary、stage_summaries、next_steps、current_node
    def compress_state(self, state: InvestigationState) -> InvestigationState:
        top_fact = state.confirmed_facts[-1].statement if state.confirmed_facts else "暂无新事实"
        top_hypothesis = state.hypotheses[0].statement if state.hypotheses else "暂无有效假设"
        summary = (
            f"第 {state.loop_count + 1} 轮已压缩："
            f"confirmed_facts={len(state.confirmed_facts)}，"
            f"top_fact={top_fact}；top_hypothesis={top_hypothesis}。"
        )
        self._append_stage_summary(state, InvestigationGraphNode.COMPRESS_STATE.value, summary)
        state.next_steps = ["进入 decide_next_step 判断继续 loop 还是收口响应。"]
        state.current_node = InvestigationGraphNode.DECIDE_NEXT_STEP
        return state

    # 决定下一步路由，保证编排器能够在 loop 和收口之间显式分支。
    # 读取：loop_count、confirmed_facts、pending_actions
    # 写入：loop_count、should_respond、next_steps、stage_summary、current_node
    def decide_next_step(self, state: InvestigationState) -> InvestigationState:
        next_loop_count = state.loop_count + 1
        state.loop_count = next_loop_count

        enough_facts = len(state.confirmed_facts) >= 6
        reached_max_loop = next_loop_count >= self._dependencies.max_loop_count
        state.should_respond = reached_max_loop or (enough_facts and next_loop_count >= 2)

        if state.should_respond:
            summary = "当前证据已达到最小收口条件，进入 generate_response。"
            state.next_steps = ["进入 generate_response 输出当前调查结论。"]
            state.current_node = InvestigationGraphNode.GENERATE_RESPONSE
        else:
            summary = "当前证据仍需补强，返回 plan_investigation 继续下一轮。"
            state.next_steps = ["返回 plan_investigation 继续下一轮调查。"]
            state.current_node = InvestigationGraphNode.PLAN_INVESTIGATION

        self._append_stage_summary(state, InvestigationGraphNode.DECIDE_NEXT_STEP.value, summary)
        return state

    # 生成最终响应摘要，保证主循环收口后能得到统一的输出对象。
    # 读取：stage_summary、pending_actions、confirmed_facts、hypotheses、loop_count
    # 写入：response_summary、status、should_respond、next_steps、stage_summary、current_node
    def generate_response(self, state: InvestigationState) -> InvestigationState:
        current_fact = state.confirmed_facts[-1].statement if state.confirmed_facts else "暂无事实"
        current_hypothesis = state.hypotheses[0].statement if state.hypotheses else "暂无假设"

        response_summary = (
            f"排障主循环已完成 {state.loop_count} 轮调查。"
            f"当前关键事实：{current_fact}。"
            f"当前首要假设：{current_hypothesis}。"
        )
        if state.pending_actions:
            response_summary += " 已生成 guarded 动作建议，后续模块可从审批分支继续接管。"

        state.response_summary = response_summary
        state.should_respond = True
        state.status = (
            InvestigationStatus.AWAITING_APPROVAL
            if state.pending_actions
            else InvestigationStatus.COMPLETED
        )
        state.next_steps = (
            ["如需继续处置，请对 pending_actions 发起审批。"]
            if state.pending_actions
            else ["当前标准场景已完成最小收口。"]
        )
        self._append_stage_summary(
            state,
            InvestigationGraphNode.GENERATE_RESPONSE.value,
            "已完成主循环收口并生成最终响应摘要。",
        )
        state.current_node = InvestigationGraphNode.GENERATE_RESPONSE
        return state

    # 追加阶段摘要并同步 stage_summary，保证每个节点都留下可追踪的压缩结果。
    def _append_stage_summary(self, state: InvestigationState, stage: str, summary: str) -> None:
        state.stage_summary = summary
        state.stage_summaries.append(
            StageSummaryRecord(
                stage=stage,
                summary=summary,
                updated_at=self._utc_now(),
            )
        )

    # 统一按工具构建占位 findings，保证后续模块拆分多 Agent 时仍可复用合并逻辑。
    def _build_finding_for_tool(self, state: InvestigationState, tool: ToolType) -> str:
        if state.scenario_id is None:
            return f"{tool.value} 已执行占位调查，当前没有标准场景数据可供分析。"

        try:
            if tool == ToolType.LOG_QUERY:
                logs = self._dependencies.log_adapter.list_logs(state.scenario_id)
                error_logs = [log for log in logs if log.level.lower() in {"error", "fatal"}]
                if error_logs:
                    return f"日志调查发现 {len(error_logs)} 条 error/fatal 记录，首条样例：{error_logs[0].message}"
                return "日志调查未发现 error/fatal 级别异常记录。"
            if tool == ToolType.METRICS_QUERY:
                metrics = self._dependencies.metrics_adapter.list_metrics(state.scenario_id)
                if metrics:
                    top_metric = max(metrics, key=lambda item: item.value)
                    return f"指标调查发现 {top_metric.metric_name} 峰值达到 {top_metric.value}{top_metric.unit}"
                return "指标调查未返回采样点。"
            if tool == ToolType.CHANGE_QUERY:
                changes = self._dependencies.change_adapter.list_changes(state.scenario_id)
                if changes:
                    latest_change = changes[0]
                    return (
                        f"变更调查发现最近一次 {latest_change.change_type} 发生在 "
                        f"{latest_change.changed_at}，版本 {latest_change.version or 'unknown'}"
                    )
                return "变更调查未发现最近变更记录。"
            if tool == ToolType.DEPENDENCY_QUERY:
                cmdb_record = self._dependencies.cmdb_adapter.get_service(state.scenario_id)
                return (
                    f"依赖调查发现服务 {cmdb_record.service} 下游依赖 {len(cmdb_record.downstreams)} 个，"
                    f"上游依赖 {len(cmdb_record.upstreams)} 个。"
                )
            if tool == ToolType.RUNBOOK_LOOKUP:
                runbook = self._dependencies.runbook_adapter.get_runbook(state.scenario_id)
                return f"知识检索确认 Runbook《{runbook.title}》可作为当前场景处理参考。"
        except ScenarioDataError:
            return f"{tool.value} 已执行占位调查，但标准场景数据暂不可用。"

        return f"{tool.value} 已执行占位调查，当前使用统一占位结论。"

    # 根据 findings 生成当前轮主假设，保证假设列表随着证据合并而更新。
    def _build_hypothesis_from_findings(self, state: InvestigationState) -> HypothesisRecord | None:
        if state.fault_type == FaultType.RELEASE_REGRESSION:
            statement = "最近变更与错误激增时间接近，优先怀疑发布回归。"
        elif state.fault_type == FaultType.DEPENDENCY_FAILURE:
            statement = "下游依赖异常可能导致主链路超时或失败。"
        elif state.fault_type == FaultType.RESOURCE_SATURATION:
            statement = "资源饱和可能导致接口延迟和错误率同时上升。"
        elif state.fault_type == FaultType.JVM_GC:
            statement = "JVM GC 抖动可能导致请求处理时间放大。"
        elif state.fault_type == FaultType.FALSE_ALARM:
            statement = "当前告警可能是噪声，需要结合更多用户影响证据确认。"
        else:
            statement = "当前问题仍需进一步收集证据才能收敛。"

        return HypothesisRecord(
            hypothesis_id=self._new_hypothesis_id(),
            statement=statement,
            confidence=0.72 if state.loop_count >= 1 else 0.58,
            supporting_evidence_ids=[item.evidence_id for item in state.evidence[-2:]],
        )

    # 生成 guarded 动作建议占位，保证后续审批流有明确挂载输入。
    def _build_pending_actions(self, fault_type: FaultType) -> list[ActionPlanRecord]:
        if fault_type != FaultType.RELEASE_REGRESSION:
            return []

        return [
            ActionPlanRecord(
                action_id=f"act-{uuid4().hex[:8]}",
                title="回滚最近一次发布",
                description="建议先回滚最近一次生产发布，用于验证错误率上升是否由变更引入。",
                risk_level=ActionRiskLevel.GUARDED,
                target="production.release",
                reason="调查结果指向最近变更与故障时间高度接近，需要保留审批挂载点。",
                requires_approval=True,
            )
        ]

    # 根据输入描述做最小故障分类，保证当前模块拥有稳定可测试的占位判定。
    def _classify_fault_type(self, problem_statement: str) -> FaultType:
        text = problem_statement.lower()
        if any(keyword in text for keyword in ["release", "rollback", "deploy", "发布", "回滚"]):
            return FaultType.RELEASE_REGRESSION
        if any(keyword in text for keyword in ["dependency", "downstream", "依赖", "下游"]):
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

    # 根据输入描述估算紧急度，保证 loop 前已有优先级信息。
    def _classify_urgency(self, problem_statement: str) -> UrgencyLevel:
        text = problem_statement.lower()
        if any(keyword in text for keyword in ["critical", "sev1", "全站", "大面积", "major"]):
            return UrgencyLevel.CRITICAL
        if any(keyword in text for keyword in ["500", "timeout", "latency", "error", "告警"]):
            return UrgencyLevel.HIGH
        if any(keyword in text for keyword in ["warning", "抖动", "波动"]):
            return UrgencyLevel.MEDIUM
        return UrgencyLevel.LOW

    # 根据输入描述估算影响范围，保证响应摘要能表达问题外溢范围。
    def _classify_impact_scope(self, problem_statement: str) -> ImpactScope:
        text = problem_statement.lower()
        if any(keyword in text for keyword in ["user", "customer", "订单", "支付", "login", "登录"]):
            return ImpactScope.USER_FACING
        if any(keyword in text for keyword in ["dependency", "依赖", "下游", "跨服务"]):
            return ImpactScope.CROSS_SERVICE
        if problem_statement.strip():
            return ImpactScope.SINGLE_SERVICE
        return ImpactScope.UNKNOWN

    # 选择当前问题需要的 Agent 角色，保证接口输出保留后续多 Agent 拆分信号。
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

    # 选择当前轮要调用的工具，保证 plan_investigation 始终输出清晰的工具计划。
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

    # 安全读取告警列表，保证缺失标准场景时不会中断整个初始化步骤。
    def _safe_list_alerts(self, scenario_id: str) -> list[object]:
        try:
            return self._dependencies.alert_adapter.list_alerts(scenario_id)
        except ScenarioDataError:
            return []

    # 安全读取工单列表，保证知识检索阶段在缺失数据时回落到占位摘要。
    def _safe_list_tickets(self, scenario_id: str) -> list[object]:
        try:
            return self._dependencies.ticket_adapter.list_tickets(scenario_id)
        except ScenarioDataError:
            return []

    # 安全读取 Runbook，保证知识检索阶段在缺失数据时继续执行。
    def _safe_get_runbook(self, scenario_id: str) -> object | None:
        try:
            return self._dependencies.runbook_adapter.get_runbook(scenario_id)
        except ScenarioDataError:
            return None

    # 安全读取 CMDB，保证初始化阶段在缺失数据时继续执行。
    def _safe_get_service(self, scenario_id: str) -> object | None:
        try:
            return self._dependencies.cmdb_adapter.get_service(scenario_id)
        except ScenarioDataError:
            return None

    # 统一生成事实标识，保证新增事实的引用格式一致。
    def _new_fact_id(self) -> str:
        return f"fact-{uuid4().hex[:8]}"

    # 统一生成证据标识，保证新增证据的引用格式一致。
    def _new_evidence_id(self) -> str:
        return f"ev-{uuid4().hex[:8]}"

    # 统一生成假设标识，保证新增假设的引用格式一致。
    def _new_hypothesis_id(self) -> str:
        return f"hyp-{uuid4().hex[:8]}"

    # 统一生成时间字符串，保证阶段摘要时间格式稳定一致。
    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()
