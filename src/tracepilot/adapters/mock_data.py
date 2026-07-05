"""TracePilot mock 场景数据读取与 adapter 实现。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from tracepilot.adapters.base import (
    AlertAdapter,
    ChangeAdapter,
    CMDBAdapter,
    LogAdapter,
    MetricsAdapter,
    RunbookAdapter,
    TicketAdapter,
)
from tracepilot.adapters.exceptions import ScenarioFileMissingError, ScenarioNotFoundError
from tracepilot.adapters.models import (
    AlertRecord,
    ChangeRecord,
    CMDBRecord,
    LogRecord,
    MetricPoint,
    RunbookRecord,
    TicketRecord,
)


class MockScenarioRepository:
    """mock 场景文件仓库。"""

    # 默认场景根目录，用于统一定位标准 mock 数据目录。
    DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "mock" / "scenarios"
    # 场景文件映射，用于声明每类数据固定使用的文件名。
    FILE_NAMES: dict[str, str] = {
        "alerts": "alerts.json",
        "logs": "logs.jsonl",
        "metrics": "metrics.csv",
        "changes": "changes.json",
        "tickets": "tickets.json",
        "cmdb": "cmdb.json",
        "runbook": "runbooks.md",
    }

    # 初始化仓库根目录，用于支持测试中替换临时目录。
    def __init__(self, root_dir: Path | None = None) -> None:
        self._root_dir = root_dir or self.DEFAULT_ROOT

    # 返回标准场景根目录，便于外部做说明或调试。
    @property
    def root_dir(self) -> Path:
        return self._root_dir

    # 列出所有场景目录，用于验证目录结构是否完整。
    def list_scenarios(self) -> list[str]:
        if not self._root_dir.exists():
            return []
        return sorted(
            item.name
            for item in self._root_dir.iterdir()
            if item.is_dir()
        )

    # 读取 JSON 数组文件，用于加载告警、变更、工单和 CMDB 数据。
    def read_json_list(self, scenario_id: str, dataset: str) -> list[dict[str, object]]:
        payload = self._read_text(scenario_id, dataset)
        data = json.loads(payload)
        return [] if data is None else list(data)

    # 读取 JSONL 文件，用于逐行加载日志数据并保持时间线顺序。
    def read_jsonl(self, scenario_id: str, dataset: str) -> list[dict[str, object]]:
        payload = self._read_text(scenario_id, dataset)
        records: list[dict[str, object]] = []
        for line in payload.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
        return records

    # 读取 CSV 文件，用于加载指标序列并解析标签列。
    def read_csv(self, scenario_id: str, dataset: str) -> list[dict[str, str]]:
        path = self._resolve_file_path(scenario_id, dataset)
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            return list(reader)

    # 读取 Markdown 文本，用于保留完整 Runbook 内容。
    def read_markdown(self, scenario_id: str, dataset: str) -> str:
        return self._read_text(scenario_id, dataset)

    # 解析并返回场景目录，目录不存在时抛出显式异常方便测试与定位。
    def _resolve_scenario_dir(self, scenario_id: str) -> Path:
        scenario_dir = self._root_dir / scenario_id
        if not scenario_dir.exists() or not scenario_dir.is_dir():
            raise ScenarioNotFoundError(f"Scenario '{scenario_id}' not found.")
        return scenario_dir

    # 解析并返回指定数据文件路径，文件缺失时抛出显式异常避免静默失败。
    def _resolve_file_path(self, scenario_id: str, dataset: str) -> Path:
        scenario_dir = self._resolve_scenario_dir(scenario_id)
        file_name = self.FILE_NAMES[dataset]
        file_path = scenario_dir / file_name
        if not file_path.exists() or not file_path.is_file():
            raise ScenarioFileMissingError(
                f"Scenario '{scenario_id}' is missing required file '{file_name}'."
            )
        return file_path

    # 读取文本文件内容，用于统一处理 UTF-8 编码与缺失文件校验。
    def _read_text(self, scenario_id: str, dataset: str) -> str:
        path = self._resolve_file_path(scenario_id, dataset)
        return path.read_text(encoding="utf-8")


class MockAlertAdapter(AlertAdapter):
    """mock 告警 adapter。"""

    # 初始化仓库依赖，用于在测试中注入临时场景目录。
    def __init__(self, repository: MockScenarioRepository | None = None) -> None:
        self._repository = repository or MockScenarioRepository()

    # 读取告警文件并转换为领域友好的结构化对象。
    def list_alerts(self, scenario_id: str) -> list[AlertRecord]:
        records = self._repository.read_json_list(scenario_id, "alerts")
        return [AlertRecord.model_validate(record) for record in records]


class MockLogAdapter(LogAdapter):
    """mock 日志 adapter。"""

    # 初始化仓库依赖，用于在测试中注入临时场景目录。
    def __init__(self, repository: MockScenarioRepository | None = None) -> None:
        self._repository = repository or MockScenarioRepository()

    # 读取 JSONL 日志并转换为日志对象，保持场景内时间线稳定。
    def list_logs(self, scenario_id: str) -> list[LogRecord]:
        records = self._repository.read_jsonl(scenario_id, "logs")
        return [LogRecord.model_validate(record) for record in records]


class MockMetricsAdapter(MetricsAdapter):
    """mock 指标 adapter。"""

    # 初始化仓库依赖，用于在测试中注入临时场景目录。
    def __init__(self, repository: MockScenarioRepository | None = None) -> None:
        self._repository = repository or MockScenarioRepository()

    # 读取 CSV 指标并解析标签字段，保证指标筛选语义一致。
    def list_metrics(self, scenario_id: str) -> list[MetricPoint]:
        rows = self._repository.read_csv(scenario_id, "metrics")
        points: list[MetricPoint] = []
        for row in rows:
            labels = self._parse_labels(row.get("labels", ""))
            points.append(
                MetricPoint(
                    timestamp=row["timestamp"],
                    scenario_id=row["scenario_id"],
                    service=row["service"],
                    metric_name=row["metric_name"],
                    value=float(row["value"]),
                    unit=row["unit"],
                    labels=labels,
                )
            )
        return points

    # 解析逗号分隔标签串，用于让 CSV 也能承载结构化维度。
    def _parse_labels(self, raw_labels: str) -> dict[str, str]:
        if not raw_labels:
            return {}
        labels: dict[str, str] = {}
        for segment in raw_labels.split(","):
            key, value = segment.split("=", maxsplit=1)
            labels[key.strip()] = value.strip()
        return labels


class MockChangeAdapter(ChangeAdapter):
    """mock 变更 adapter。"""

    # 初始化仓库依赖，用于在测试中注入临时场景目录。
    def __init__(self, repository: MockScenarioRepository | None = None) -> None:
        self._repository = repository or MockScenarioRepository()

    # 读取变更文件并转换为结构化变更对象，便于和告警时间线比对。
    def list_changes(self, scenario_id: str) -> list[ChangeRecord]:
        records = self._repository.read_json_list(scenario_id, "changes")
        return [ChangeRecord.model_validate(record) for record in records]


class MockTicketAdapter(TicketAdapter):
    """mock 工单 adapter。"""

    # 初始化仓库依赖，用于在测试中注入临时场景目录。
    def __init__(self, repository: MockScenarioRepository | None = None) -> None:
        self._repository = repository or MockScenarioRepository()

    # 读取工单文件并转换为工单对象，便于还原人工处置上下文。
    def list_tickets(self, scenario_id: str) -> list[TicketRecord]:
        records = self._repository.read_json_list(scenario_id, "tickets")
        return [TicketRecord.model_validate(record) for record in records]


class MockRunbookAdapter(RunbookAdapter):
    """mock Runbook adapter。"""

    # 初始化仓库依赖，用于在测试中注入临时场景目录。
    def __init__(self, repository: MockScenarioRepository | None = None) -> None:
        self._repository = repository or MockScenarioRepository()

    # 读取 Runbook 文档并包装为单条记录，便于统一 adapter 接口返回。
    def get_runbook(self, scenario_id: str) -> RunbookRecord:
        content = self._repository.read_markdown(scenario_id, "runbook")
        title = self._extract_title(content)
        service = self._extract_service(content)
        return RunbookRecord(
            scenario_id=scenario_id,
            title=title,
            service=service,
            content=content,
        )

    # 从 Markdown 标题解析 Runbook 标题，保证文档内容和结构化字段一致。
    def _extract_title(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return "Untitled Runbook"

    # 从约定元数据解析服务名，避免在文档外重复维护服务字段。
    def _extract_service(self, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("service:"):
                return stripped.split(":", maxsplit=1)[1].strip()
        return "unknown"


class MockCMDBAdapter(CMDBAdapter):
    """mock CMDB adapter。"""

    # 初始化仓库依赖，用于在测试中注入临时场景目录。
    def __init__(self, repository: MockScenarioRepository | None = None) -> None:
        self._repository = repository or MockScenarioRepository()

    # 读取 CMDB 文件并返回单条记录，确保服务拓扑和责任信息可稳定获得。
    def get_service(self, scenario_id: str) -> CMDBRecord:
        records = self._repository.read_json_list(scenario_id, "cmdb")
        if not records:
            raise ScenarioFileMissingError(
                f"Scenario '{scenario_id}' has empty CMDB data."
            )
        return CMDBRecord.model_validate(records[0])
