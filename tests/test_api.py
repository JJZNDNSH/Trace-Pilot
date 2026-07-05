"""TracePilot Phase 1 接口测试。"""

from fastapi.testclient import TestClient

from tracepilot.main import create_app


# 创建独立测试客户端，确保每个测试拥有隔离的内存状态。
def build_client() -> TestClient:
    return TestClient(create_app())


# 验证 OpenAPI 已暴露本次新增的三个接口，保证 Swagger 可见性。
def test_openapi_exposes_phase_one_routes() -> None:
    client = build_client()

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/investigate" in paths
    assert "/actions/approve" in paths
    assert "/health" in paths


# 验证 investigate 响应结构符合规划文档，并在发布回归场景返回待审批动作。
def test_investigate_returns_contract() -> None:
    client = build_client()

    response = client.post(
        "/investigate",
        json={
            "user_id": "alice",
            "environment": "production",
            "scenario_id": "order_api_500_after_release",
            "problem_statement": "发布后订单 API 500 激增，需要确认是否回滚。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fault_type"] == "release_regression"
    assert payload["urgency"] == "high"
    assert payload["selected_agents"] == ["TriageAgent", "ChangeAgent", "LogsAgent"]
    assert payload["selected_tools"] == ["change_query", "log_query", "runbook_lookup"]
    assert payload["pending_actions"][0]["risk_level"] == "guarded"
    assert payload["latency_ms"] >= 0


# 验证审批接口会更新状态对象，并返回模拟执行结果而非真实工具调用。
def test_approve_action_updates_state() -> None:
    client = build_client()

    create_response = client.post(
        "/investigate",
        json={
            "user_id": "bob",
            "environment": "production",
            "scenario_id": "order_api_500_after_release",
            "problem_statement": "release 后支付接口 500 增长，考虑 rollback。",
        },
    )
    created_payload = create_response.json()
    pending_action = created_payload["pending_actions"][0]

    approve_response = client.post(
        "/actions/approve",
        json={
            "session_id": created_payload["session_id"],
            "action_id": pending_action["action_id"],
            "approved": True,
            "approver_id": "oncall_lead",
            "note": "先按回滚方案模拟执行。",
        },
    )

    assert approve_response.status_code == 200
    payload = approve_response.json()
    assert payload["approved"] is True
    assert payload["execution_result"]["status"] == "simulated"
    assert payload["execution_result"]["simulated"] is True
    assert payload["updated_state"]["approved_actions"][0]["action_id"] == pending_action["action_id"]
    assert payload["updated_state"]["pending_actions"] == []
    assert payload["updated_state"]["current_node"] == "execute_actions"


# 验证健康检查接口可用，满足基础启动联调需求。
def test_health_endpoint() -> None:
    client = build_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
