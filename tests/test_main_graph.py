"""TracePilot 自研编排器测试。"""

from fastapi.testclient import TestClient

from tracepilot.graph import build_investigation_graph
from tracepilot.main import create_app
from tracepilot.schemas.investigation import InvestigateRequest
from tracepilot.services.investigation_service import InMemoryInvestigationStore, InvestigationService


# 构建独立服务，保证每个测试都使用隔离的状态存储。
def build_service() -> tuple[InvestigationService, InMemoryInvestigationStore]:
    store = InMemoryInvestigationStore()
    return InvestigationService(store=store, runner=build_investigation_graph()), store


# 验证编排器可以执行完整的“初始化 + Loop + 收口”流程。
def test_runner_executes_standard_scenario() -> None:
    runner = build_investigation_graph()

    result = runner.run(
        InvestigateRequest(
            user_id="carol",
            environment="production",
            scenario_id="order_api_500_after_release",
            problem_statement="release 后订单 API 500 增长，需要定位是否与发布相关。",
        )
    )

    assert result.state.current_node == "generate_response"
    assert result.state.should_respond is True
    assert result.state.loop_count == 2
    assert result.response.summary.startswith("排障主循环已完成 2 轮调查。")


# 验证 investigate 服务会保存编排后的最终状态，保证 state 能跨步骤传递。
def test_service_investigate_persists_state_after_orchestration() -> None:
    service, store = build_service()

    response = service.investigate(
        InvestigateRequest(
            user_id="dave",
            environment="production",
            scenario_id="payment_timeout_db_saturation",
            problem_statement="支付超时并伴随数据库饱和，需要确认是否为资源问题。",
        )
    )
    stored_state = store.get(response.session_id)

    assert stored_state is not None
    assert stored_state.knowledge_summary is not None
    assert stored_state.stage_summary is not None
    assert stored_state.loop_count == 2
    assert len(stored_state.confirmed_facts) >= 4
    assert stored_state.response_summary is not None


# 验证 decide_next_step 至少触发一次 loop，而不是单次直线执行。
def test_decide_next_step_triggers_additional_loop() -> None:
    runner = build_investigation_graph()

    result = runner.run(
        InvestigateRequest(
            user_id="erin",
            environment="production",
            scenario_id="order_api_500_after_release",
            problem_statement="发布后订单 API 500 激增，需要排查回归来源。",
        )
    )
    plan_stage_count = sum(
        1
        for item in result.state.stage_summaries
        if item.stage == "plan_investigation"
    )

    assert result.state.loop_count == 2
    assert plan_stage_count >= 2


# 验证 investigate 接口已经接到自研编排器执行入口。
def test_investigate_endpoint_runs_main_graph() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/investigate",
        json={
            "user_id": "frank",
            "environment": "production",
            "scenario_id": "order_api_500_after_release",
            "problem_statement": "release 后订单 API 500 增长，需要定位是否与发布相关。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"].startswith("排障主循环已完成 2 轮调查。")
    assert payload["selected_tools"] == ["change_query", "log_query", "runbook_lookup"]
    assert payload["latency_ms"] >= 0
