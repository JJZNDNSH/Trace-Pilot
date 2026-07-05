"""TracePilot 自研 Agent Loop 编排执行入口。"""

from __future__ import annotations

from dataclasses import dataclass

from tracepilot.domain.state import InvestigationState
from tracepilot.graph.nodes import (
    DEFAULT_MAX_LOOP_COUNT,
    InvestigationGraphDependencies,
    InvestigationGraphNodes,
)
from tracepilot.schemas.investigation import InvestigateRequest, InvestigateResponse


@dataclass(slots=True)
class InvestigationExecutionResult:
    """编排器执行结果。"""

    # 最终状态对象，用于存储层持久化和后续审批流恢复。
    state: InvestigationState
    # 最终响应对象，用于直接返回 investigate 接口。
    response: InvestigateResponse


class InvestigationGraphRunner:
    """自研 Agent Loop 编排器。"""

    # 初始化编排器并注入节点集合，保证步骤编排与步骤实现解耦。
    def __init__(
        self,
        dependencies: InvestigationGraphDependencies | None = None,
        nodes: InvestigationGraphNodes | None = None,
    ) -> None:
        self._nodes = nodes or InvestigationGraphNodes(dependencies)

    # 执行初始化阶段、主循环和最终收口，输出统一的状态与响应对象。
    def run(self, request: InvestigateRequest) -> InvestigationExecutionResult:
        state = self._nodes.build_initial_state(request)
        state = self._nodes.load_context(state)
        state = self._nodes.classify_incident(state)
        state = self._nodes.retrieve_knowledge(state)

        # 这里只实现 loop 或收口两条路径，并预留后续 guarded 审批分支挂载点。
        while True:
            state = self._nodes.plan_investigation(state)
            state = self._nodes.run_investigation_step(state)
            state = self._nodes.merge_findings(state)
            state = self._nodes.compress_state(state)
            state = self._nodes.decide_next_step(state)

            # 当前模块显式保留分支判断，后续模块可在这里插入审批流或并行路由。
            next_stage = self._route_after_decision(state)
            if next_stage == "respond":
                break

        state = self._nodes.generate_response(state)
        response = self._build_response(state)
        return InvestigationExecutionResult(state=state, response=response)

    # 根据 should_respond 返回路由键，显式体现 loop 和收口两条分支。
    def _route_after_decision(self, state: InvestigationState) -> str:
        if state.should_respond:
            return "respond"
        return "loop"

    # 从最终状态组装 investigate 响应，保证 API 契约与编排器内部状态解耦。
    def _build_response(self, state: InvestigationState) -> InvestigateResponse:
        return InvestigateResponse(
            session_id=state.session_id,
            fault_type=state.fault_type,
            urgency=state.urgency,
            selected_agents=state.selected_agents,
            selected_tools=state.selected_tools,
            summary=state.response_summary or "当前调查已完成最小收口。",
            confirmed_facts=state.confirmed_facts,
            hypotheses=state.hypotheses,
            next_steps=state.next_steps,
            pending_actions=state.pending_actions,
            escalated=state.escalated,
            latency_ms=0,
        )


# 构建默认编排器入口，供服务层统一复用。
def build_investigation_graph(
    dependencies: InvestigationGraphDependencies | None = None,
) -> InvestigationGraphRunner:
    return InvestigationGraphRunner(dependencies=dependencies)
