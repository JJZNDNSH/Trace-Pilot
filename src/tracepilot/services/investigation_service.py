"""调查与审批服务。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter

from fastapi import HTTPException, status

from tracepilot.domain.enums import InvestigationGraphNode, InvestigationStatus
from tracepilot.domain.models import AuditRecord, ExecutionResultRecord
from tracepilot.domain.state import InvestigationState
from tracepilot.graph import InvestigationGraphRunner, build_investigation_graph
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

    # 保存最新状态，保证审批接口能够读取并更新同一会话。
    def save(self, state: InvestigationState) -> None:
        self.states[state.session_id] = state

    # 按会话读取状态，找不到时返回 None 交由服务层统一报错。
    def get(self, session_id: str) -> InvestigationState | None:
        return self.states.get(session_id)


class InvestigationService:
    """排障接口服务。"""

    # 初始化服务并注入存储与编排器，保证服务层只负责编排入口和状态持久化。
    def __init__(
        self,
        store: InMemoryInvestigationStore | None = None,
        runner: InvestigationGraphRunner | None = None,
    ) -> None:
        self._store = store or InMemoryInvestigationStore()
        self._runner = runner or build_investigation_graph()

    # 执行 investigate 编排入口，并把最终状态保存给后续审批流复用。
    def investigate(self, request: InvestigateRequest) -> InvestigateResponse:
        started_at = perf_counter()
        execution = self._runner.run(request)

        # 服务层补充接口耗时，避免把 HTTP 侧指标计算塞进编排器内部。
        latency_ms = int((perf_counter() - started_at) * 1000)
        response = execution.response.model_copy(update={"latency_ms": latency_ms})
        self._store.save(execution.state)
        return response

    # 处理动作审批，并通过内存状态模拟审批后的恢复入口。
    def approve_action(self, request: ApproveActionRequest) -> ApproveActionResponse:
        state = self._store.get(request.session_id)
        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{request.session_id}' not found.",
            )

        # 只允许审批当前待审批列表中的动作，避免误更新无关状态。
        action = next((item for item in state.pending_actions if item.action_id == request.action_id), None)
        if action is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pending action '{request.action_id}' not found.",
            )

        # 先从待审批列表移除动作，保证状态始终反映最新的审批结果。
        state.pending_actions = [item for item in state.pending_actions if item.action_id != request.action_id]

        if request.approved:
            # 批准后把动作转移到 approved_actions，为后续 execute_actions 挂载点保留输入。
            state.approved_actions.append(action)
            state.current_node = InvestigationGraphNode.EXECUTE_ACTIONS
            state.status = InvestigationStatus.IN_PROGRESS
            execution_result = ExecutionResultRecord(
                status="simulated",
                message="动作已通过审批，当前阶段仅记录模拟执行结果，未调用真实执行工具。",
                simulated=True,
            )
            updated_summary = "待审批动作已批准，状态已切换到 execute_actions 占位节点。"
        else:
            # 拒绝后回到 generate_response，保证状态机不会停留在不可继续执行的节点。
            state.current_node = InvestigationGraphNode.GENERATE_RESPONSE
            state.status = InvestigationStatus.COMPLETED
            execution_result = ExecutionResultRecord(
                status="skipped",
                message="动作未获批准，系统保留审批结果并结束本次模拟执行。",
                simulated=True,
            )
            updated_summary = "待审批动作已拒绝，状态已回到 generate_response 占位节点。"

        # 如果还有剩余待审批动作，就继续保持待审批状态，方便后续逐条审批。
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

    # 统一生成 UTC 时间字符串，避免不同步骤各自处理时间格式。
    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()
