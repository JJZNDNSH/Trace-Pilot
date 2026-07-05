"""TracePilot 模块 3 工具层测试。"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tracepilot.adapters import (
    AlertRecord,
    LogRecord,
    MockAlertAdapter,
    MockChangeAdapter,
    MockCMDBAdapter,
    MockLogAdapter,
    MockMetricsAdapter,
    MockRunbookAdapter,
    MockTicketAdapter,
)
from tracepilot.adapters.base import AlertAdapter, LogAdapter
from tracepilot.domain.enums import ActionRiskLevel
from tracepilot.tools import ToolAdapterBundle, ToolCallStatus, build_default_tool_registry
from tracepilot.tools.registry import ToolDefinition, ToolRegistry


class FailingAlertAdapter(AlertAdapter):
    """用于验证 fallback 的失败告警 adapter。"""

    # 抛出固定异常，用于验证查询工具在异常时会返回 fallback 结果。
    def list_alerts(self, scenario_id: str) -> list[AlertRecord]:
        raise RuntimeError(f"alert backend unavailable for {scenario_id}")


class SlowLogAdapter(LogAdapter):
    """用于验证 timeout 的慢日志 adapter。"""

    # 先等待再返回结果，用于验证超时后能返回 fallback 而不是阻塞主流程。
    def list_logs(self, scenario_id: str) -> list[LogRecord]:
        time.sleep(0.05)
        return MockLogAdapter().list_logs(scenario_id)


class MinimalToolInput(BaseModel):
    """最小测试工具输入。"""

    # 禁止额外字段，用于保持测试工具 schema 明确。
    model_config = ConfigDict(extra="forbid")

    # 任意参数，用于触发最小工具调用。
    value: str = Field(..., description="任意参数。")


# 构建默认 adapter 集合并允许覆写单个依赖，用于测试 fallback 和 timeout 场景。
def build_tool_adapters(
    *,
    alert_adapter: AlertAdapter | None = None,
    log_adapter: LogAdapter | None = None,
) -> ToolAdapterBundle:
    return ToolAdapterBundle(
        alert_adapter=alert_adapter or MockAlertAdapter(),
        log_adapter=log_adapter or MockLogAdapter(),
        metrics_adapter=MockMetricsAdapter(),
        change_adapter=MockChangeAdapter(),
        ticket_adapter=MockTicketAdapter(),
        runbook_adapter=MockRunbookAdapter(),
        cmdb_adapter=MockCMDBAdapter(),
    )


# 验证 13 个内置工具都已注册，并且每个工具都暴露了明确 schema。
def test_builtin_tool_registry_exposes_required_tools_and_schema() -> None:
    registry = build_default_tool_registry()

    specs = registry.list_tools()
    tool_names = [spec.name for spec in specs]

    assert tool_names == [
        "clear_cache",
        "disable_feature_flag",
        "get_incident_timeline",
        "get_recent_changes",
        "get_service_dependencies",
        "query_metrics",
        "rerun_health_check",
        "restart_service",
        "rollback_release",
        "search_alerts",
        "search_logs",
        "search_runbooks",
        "search_tickets",
    ]
    assert all(spec.input_schema.get("properties") for spec in specs)


# 验证查询类工具能够从 mock adapter 读取数据，并且缓存与统计会生效。
def test_query_tools_read_mock_data_and_cache_stats_work() -> None:
    registry = build_default_tool_registry(query_cache_ttl_seconds=60)

    alerts_response = registry.invoke(
        "search_alerts",
        {
            "scenario_id": "order_api_500_after_release",
            "service": "order-api",
        },
    )
    cached_alerts_response = registry.invoke(
        "search_alerts",
        {
            "scenario_id": "order_api_500_after_release",
            "service": "order-api",
        },
    )
    logs_response = registry.invoke(
        "search_logs",
        {
            "scenario_id": "order_api_500_after_release",
            "level": "ERROR",
            "keyword": "KeyError",
        },
    )
    metrics_response = registry.invoke(
        "query_metrics",
        {
            "scenario_id": "order_api_500_after_release",
            "metric_name": "request_latency_p95",
        },
    )
    changes_response = registry.invoke(
        "get_recent_changes",
        {
            "scenario_id": "order_api_500_after_release",
            "change_type": "release",
        },
    )
    tickets_response = registry.invoke(
        "search_tickets",
        {
            "scenario_id": "order_api_500_after_release",
            "keyword": "回滚",
        },
    )
    dependencies_response = registry.invoke(
        "get_service_dependencies",
        {
            "scenario_id": "order_api_500_after_release",
        },
    )
    runbooks_response = registry.invoke(
        "search_runbooks",
        {
            "scenario_id": "order_api_500_after_release",
            "keyword": "发布后",
        },
    )
    timeline_response = registry.invoke(
        "get_incident_timeline",
        {
            "scenario_id": "order_api_500_after_release",
            "service": "order-api",
        },
    )

    assert alerts_response.status == ToolCallStatus.SUCCESS
    assert alerts_response.data["count"] == 1
    assert "发布后" in alerts_response.data["items"][0]["summary"]
    assert cached_alerts_response.runtime.from_cache is True
    assert cached_alerts_response.stats.cache_hits == 1
    assert cached_alerts_response.stats.total_calls == 2
    assert logs_response.status == ToolCallStatus.SUCCESS
    assert logs_response.data["count"] >= 2
    assert metrics_response.data["count"] == 2
    assert changes_response.data["items"][0]["change_type"] == "release"
    assert tickets_response.data["items"][0]["priority"] == "P1"
    assert "payment-service" in dependencies_response.data["downstreams"]
    assert runbooks_response.data["items"][0]["service"] == "order-api"
    assert timeline_response.data["count"] >= 4
    assert timeline_response.data["items"][0]["source_type"] == "change"


# 验证查询工具在 adapter 异常时会走 fallback，并带上结构化降级标记。
def test_query_tool_returns_fallback_when_adapter_raises() -> None:
    adapters = build_tool_adapters(alert_adapter=FailingAlertAdapter())
    registry = build_default_tool_registry(adapters=adapters)

    response = registry.invoke(
        "search_alerts",
        {
            "scenario_id": "order_api_500_after_release",
            "service": "order-api",
        },
    )

    assert response.status == ToolCallStatus.FALLBACK
    assert response.runtime.used_fallback is True
    assert response.error == "alert backend unavailable for order_api_500_after_release"
    assert response.data["items"] == []
    assert response.stats.fallback_calls == 1


# 验证查询工具在超时场景下也会走 fallback，并正确累积 timeout 统计。
def test_query_tool_timeout_returns_fallback_and_updates_timeout_stats() -> None:
    adapters = build_tool_adapters(log_adapter=SlowLogAdapter())
    registry = build_default_tool_registry(
        adapters=adapters,
        query_timeout_seconds=0.01,
    )

    response = registry.invoke(
        "search_logs",
        {
            "scenario_id": "order_api_500_after_release",
        },
    )

    assert response.status == ToolCallStatus.FALLBACK
    assert response.runtime.timed_out is True
    assert response.runtime.used_fallback is True
    assert response.stats.timeout_calls == 1
    assert response.stats.fallback_calls == 1


# 验证 guarded 执行类工具会返回结构化审批标记，而 auto 工具可直接返回 mock 结果。
def test_execution_tools_return_expected_risk_markers() -> None:
    registry = build_default_tool_registry()

    guarded_response = registry.invoke(
        "restart_service",
        {
            "service": "order-api",
            "environment": "production",
            "reason": "错误率持续升高。",
        },
    )
    auto_response = registry.invoke(
        "rerun_health_check",
        {
            "service": "order-api",
            "environment": "production",
            "check_name": "readiness",
        },
    )

    assert guarded_response.status == ToolCallStatus.GUARDED
    assert guarded_response.governance.risk_level == ActionRiskLevel.GUARDED
    assert guarded_response.governance.requires_approval is True
    assert guarded_response.data["execution_mode"] == "mock"
    assert guarded_response.stats.guarded_calls == 1
    assert auto_response.status == ToolCallStatus.SUCCESS
    assert auto_response.governance.risk_level == ActionRiskLevel.AUTO
    assert auto_response.governance.requires_approval is False
    assert auto_response.data["simulated"] is True


# 验证 denied 动作会被注册表直接拒绝，且处理函数不会被误执行。
def test_denied_tool_returns_structured_marker() -> None:
    called = {"value": False}

    def denied_handler(tool_input: BaseModel) -> dict[str, Any]:
        called["value"] = True
        return {"value": tool_input.model_dump(mode="json")}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="dangerous_tool",
            description="测试用 denied 工具。",
            risk_level=ActionRiskLevel.DENIED,
            input_model=MinimalToolInput,
            handler=denied_handler,
        )
    )

    response = registry.invoke("dangerous_tool", {"value": "drop database"})

    assert response.status == ToolCallStatus.DENIED
    assert response.governance.denied is True
    assert response.data is None
    assert response.stats.denied_calls == 1
    assert called["value"] is False


# 验证未配置 fallback 的异常工具会返回结构化失败结果，而不是抛出未处理异常。
def test_tool_failure_without_fallback_is_structured() -> None:
    def failing_handler(tool_input: BaseModel) -> dict[str, Any]:
        raise RuntimeError(f"unexpected failure: {tool_input.model_dump(mode='json')['value']}")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="failing_tool",
            description="测试用失败工具。",
            risk_level=ActionRiskLevel.AUTO,
            input_model=MinimalToolInput,
            handler=failing_handler,
        )
    )

    response = registry.invoke("failing_tool", {"value": "boom"})

    assert response.status == ToolCallStatus.FAILED
    assert response.runtime.used_fallback is False
    assert response.error == "unexpected failure: boom"
    assert response.stats.failed_calls == 1
