# TracePilot Phase 1 对外接口说明

## 范围
- 本阶段只提供 `POST /investigate`、`POST /actions/approve`、`GET /health`。
- 本阶段只完成领域模型、Pydantic 契约、FastAPI 路由骨架和最小测试。
- 本阶段不接真实工具、不实现完整 Agent 逻辑、不改 Skills / Monitor / Eval。

## 启动方式
```bash
python -m pip install -e .[dev]
python -m uvicorn tracepilot.main:app --app-dir src --reload
```

启动后可访问：
- Swagger UI：`http://127.0.0.1:8000/docs`
- OpenAPI：`http://127.0.0.1:8000/openapi.json`

## 1. POST /investigate

请求体：
```json
{
  "user_id": "alice",
  "environment": "production",
  "scenario_id": "order_api_500_after_release",
  "problem_statement": "发布后订单 API 500 激增，需要确认是否回滚。"
}
```

响应体字段：
- `session_id`：排障会话 ID
- `fault_type`：故障域分类
- `urgency`：紧急度
- `selected_agents`：已选择 Agent 列表
- `selected_tools`：已选择工具列表
- `summary`：当前阶段总结
- `confirmed_facts`：已确认事实
- `hypotheses`：当前假设
- `next_steps`：建议下一步
- `pending_actions`：待审批动作
- `escalated`：是否已升级
- `latency_ms`：接口耗时

说明：
- 当前阶段只返回骨架化规划结果。
- 如果识别到发布回归特征，会返回一个 `guarded` 的待审批动作示例。

## 2. POST /actions/approve

请求体：
```json
{
  "session_id": "replace-with-session-id",
  "action_id": "replace-with-action-id",
  "approved": true,
  "approver_id": "oncall_lead",
  "note": "先按回滚方案模拟执行。"
}
```

响应体字段：
- `session_id`：排障会话 ID
- `action_id`：动作 ID
- `approved`：审批结论
- `execution_result`：模拟执行结果
- `updated_summary`：更新后的状态说明
- `updated_state`：完整 `InvestigationState`
- `audit_record`：审批审计记录

说明：
- 当前阶段只模拟审批后的状态迁移。
- 不会调用真实执行工具。

## 3. GET /health

响应体：
```json
{
  "service": "TracePilot",
  "status": "ok",
  "version": "0.1.0"
}
```

## 领域模型说明
- `InvestigationState`：LangGraph 主状态骨架，完整覆盖 `PLAN.md` 当前阶段要求的核心字段。
- `FaultType` / `UrgencyLevel` / `ImpactScope`：故障分类与排障路由基础枚举。
- `AgentType` / `ToolType` / `ActionRiskLevel`：Agent、工具和审批治理所需的统一契约。
- `InvestigationGraphNode`：后续 LangGraph 节点名常量，避免后续模块重复改接口层。

## 验证方式
```bash
pytest
```

验证关注点：
- `/openapi.json` 中能看到三个接口。
- `/investigate` 返回字段与文档一致。
- `/actions/approve` 能返回 `updated_state` 和 `audit_record`。
- `/health` 可用于基础探活。
