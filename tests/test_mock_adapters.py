"""TracePilot 模块 2 adapter 与 mock 数据读取测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tracepilot.adapters import (
    MockAlertAdapter,
    MockChangeAdapter,
    MockCMDBAdapter,
    MockLogAdapter,
    MockMetricsAdapter,
    MockRunbookAdapter,
    MockScenarioRepository,
    MockTicketAdapter,
    ScenarioFileMissingError,
    ScenarioNotFoundError,
)


# 创建标准场景目录，用于复用同一套临时 mock 数据结构。
def create_scenario_dir(root_dir: Path, scenario_id: str) -> Path:
    scenario_dir = root_dir / scenario_id
    scenario_dir.mkdir(parents=True, exist_ok=True)
    return scenario_dir


# 写入标准必需文件，用于构造最小可读取场景或空数据场景。
def write_standard_files(
    scenario_dir: Path,
    *,
    alerts: str = "[]",
    logs: str = "",
    metrics: str = "timestamp,scenario_id,service,metric_name,value,unit,labels\n",
    changes: str = "[]",
    tickets: str = "[]",
    cmdb: str = "[]",
    runbook: str = "# Empty Runbook\nservice: empty-service\n",
) -> None:
    (scenario_dir / "alerts.json").write_text(alerts, encoding="utf-8")
    (scenario_dir / "logs.jsonl").write_text(logs, encoding="utf-8")
    (scenario_dir / "metrics.csv").write_text(metrics, encoding="utf-8")
    (scenario_dir / "changes.json").write_text(changes, encoding="utf-8")
    (scenario_dir / "tickets.json").write_text(tickets, encoding="utf-8")
    (scenario_dir / "cmdb.json").write_text(cmdb, encoding="utf-8")
    (scenario_dir / "runbooks.md").write_text(runbook, encoding="utf-8")


# 创建共享仓库与 adapter 实例，用于保证同一组测试读取同一目录。
def build_adapters(root_dir: Path) -> dict[str, object]:
    repository = MockScenarioRepository(root_dir=root_dir)
    return {
        "repository": repository,
        "alerts": MockAlertAdapter(repository),
        "logs": MockLogAdapter(repository),
        "metrics": MockMetricsAdapter(repository),
        "changes": MockChangeAdapter(repository),
        "tickets": MockTicketAdapter(repository),
        "runbook": MockRunbookAdapter(repository),
        "cmdb": MockCMDBAdapter(repository),
    }


# 验证真实场景数据可被全部 adapter 稳定读取，并且关键语义保持一致。
def test_mock_adapters_read_built_in_scenarios_successfully() -> None:
    repository = MockScenarioRepository()
    alert_adapter = MockAlertAdapter(repository)
    log_adapter = MockLogAdapter(repository)
    metrics_adapter = MockMetricsAdapter(repository)
    change_adapter = MockChangeAdapter(repository)
    ticket_adapter = MockTicketAdapter(repository)
    runbook_adapter = MockRunbookAdapter(repository)
    cmdb_adapter = MockCMDBAdapter(repository)

    scenario_names = repository.list_scenarios()
    assert "order_api_500_after_release" in scenario_names
    assert "payment_timeout_db_saturation" in scenario_names

    order_alerts = alert_adapter.list_alerts("order_api_500_after_release")
    order_logs = log_adapter.list_logs("order_api_500_after_release")
    order_metrics = metrics_adapter.list_metrics("order_api_500_after_release")
    order_changes = change_adapter.list_changes("order_api_500_after_release")
    order_tickets = ticket_adapter.list_tickets("order_api_500_after_release")
    order_runbook = runbook_adapter.get_runbook("order_api_500_after_release")
    order_cmdb = cmdb_adapter.get_service("order_api_500_after_release")

    assert len(order_alerts) == 1
    assert len(order_logs) >= 3
    assert len(order_metrics) >= 4
    assert len(order_changes) == 1
    assert len(order_tickets) == 1
    assert order_runbook.service == "order-api"
    assert order_cmdb.service == "order-api"
    assert order_changes[0].changed_at < order_alerts[0].fired_at
    assert "发布后" in order_alerts[0].summary
    assert any(log.fields.get("http_status") == 500 for log in order_logs)
    assert any(
        metric.metric_name == "http_requests_total"
        and metric.labels.get("status") == "500"
        and metric.value >= 200
        for metric in order_metrics
    )
    assert "回滚" in order_tickets[0].description
    assert "发布后" in order_runbook.content

    payment_alerts = alert_adapter.list_alerts("payment_timeout_db_saturation")
    payment_logs = log_adapter.list_logs("payment_timeout_db_saturation")
    payment_metrics = metrics_adapter.list_metrics("payment_timeout_db_saturation")
    payment_changes = change_adapter.list_changes("payment_timeout_db_saturation")
    payment_tickets = ticket_adapter.list_tickets("payment_timeout_db_saturation")
    payment_runbook = runbook_adapter.get_runbook("payment_timeout_db_saturation")
    payment_cmdb = cmdb_adapter.get_service("payment_timeout_db_saturation")

    assert len(payment_alerts) == 1
    assert len(payment_logs) >= 3
    assert len(payment_metrics) >= 4
    assert len(payment_changes) == 1
    assert len(payment_tickets) == 1
    assert payment_runbook.service == "payment-service"
    assert payment_cmdb.service == "payment-service"
    assert payment_changes[0].change_type == "config"
    assert any("DB saturation" in log.message or "Database pool" in log.message for log in payment_logs)
    assert any(
        metric.metric_name == "db_connection_pool_usage" and metric.value >= 0.95
        for metric in payment_metrics
    )
    assert "数据库" in payment_tickets[0].description
    assert "连接池" in payment_runbook.content


# 验证空数据场景下各 adapter 返回稳定空结果，不会意外抛错。
def test_mock_adapters_handle_empty_data(tmp_path: Path) -> None:
    temp_root = tmp_path / "tracepilot_mock_empty"
    temp_root.mkdir(parents=True, exist_ok=True)
    scenario_dir = create_scenario_dir(temp_root, "empty_scenario")
    write_standard_files(
        scenario_dir,
        cmdb=json.dumps(
            [
                {
                    "service": "empty-service",
                    "scenario_id": "empty_scenario",
                    "owner_team": "platform",
                    "environment": "test",
                    "repository": "git@example.com:tracepilot/empty-service.git",
                    "upstreams": [],
                    "downstreams": [],
                    "oncall_team": "platform-oncall",
                    "notes": "用于测试空数据读取。",
                }
            ],
            ensure_ascii=False,
        ),
    )
    adapters = build_adapters(temp_root)

    assert adapters["alerts"].list_alerts("empty_scenario") == []
    assert adapters["logs"].list_logs("empty_scenario") == []
    assert adapters["metrics"].list_metrics("empty_scenario") == []
    assert adapters["changes"].list_changes("empty_scenario") == []
    assert adapters["tickets"].list_tickets("empty_scenario") == []
    assert adapters["runbook"].get_runbook("empty_scenario").title == "Empty Runbook"
    assert adapters["cmdb"].get_service("empty_scenario").service == "empty-service"


# 验证场景目录不存在时会抛出显式异常，避免读取失败被静默吞掉。
def test_mock_adapters_raise_when_scenario_missing(tmp_path: Path) -> None:
    temp_root = tmp_path / "tracepilot_mock_missing_scenario"
    temp_root.mkdir(parents=True, exist_ok=True)
    adapters = build_adapters(temp_root)

    with pytest.raises(ScenarioNotFoundError):
        adapters["alerts"].list_alerts("missing_scenario")


# 验证缺少标准文件时会抛出显式异常，便于快速定位目录结构问题。
def test_mock_adapters_raise_when_required_file_missing(tmp_path: Path) -> None:
    temp_root = tmp_path / "tracepilot_mock_missing_file"
    temp_root.mkdir(parents=True, exist_ok=True)
    scenario_dir = create_scenario_dir(temp_root, "broken_scenario")
    write_standard_files(scenario_dir)
    (scenario_dir / "logs.jsonl").unlink()
    adapters = build_adapters(temp_root)

    with pytest.raises(ScenarioFileMissingError):
        adapters["logs"].list_logs("broken_scenario")


# 验证空 CMDB 文件会抛出显式异常，避免返回无意义的默认服务记录。
def test_mock_cmdb_adapter_raises_when_cmdb_is_empty(tmp_path: Path) -> None:
    temp_root = tmp_path / "tracepilot_mock_empty_cmdb"
    temp_root.mkdir(parents=True, exist_ok=True)
    scenario_dir = create_scenario_dir(temp_root, "empty_cmdb_scenario")
    write_standard_files(scenario_dir)
    adapters = build_adapters(temp_root)

    with pytest.raises(ScenarioFileMissingError):
        adapters["cmdb"].get_service("empty_cmdb_scenario")
