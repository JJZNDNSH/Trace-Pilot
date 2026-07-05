"""TracePilot adapter 抽象接口定义。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from tracepilot.adapters.models import (
    AlertRecord,
    ChangeRecord,
    CMDBRecord,
    LogRecord,
    MetricPoint,
    RunbookRecord,
    TicketRecord,
)


class AlertAdapter(ABC):
    """告警查询 adapter 抽象。"""

    @abstractmethod
    def list_alerts(self, scenario_id: str) -> list[AlertRecord]:
        """读取指定场景的告警记录。"""


class LogAdapter(ABC):
    """日志查询 adapter 抽象。"""

    @abstractmethod
    def list_logs(self, scenario_id: str) -> list[LogRecord]:
        """读取指定场景的日志记录。"""


class MetricsAdapter(ABC):
    """指标查询 adapter 抽象。"""

    @abstractmethod
    def list_metrics(self, scenario_id: str) -> list[MetricPoint]:
        """读取指定场景的指标记录。"""


class ChangeAdapter(ABC):
    """变更查询 adapter 抽象。"""

    @abstractmethod
    def list_changes(self, scenario_id: str) -> list[ChangeRecord]:
        """读取指定场景的变更记录。"""


class TicketAdapter(ABC):
    """工单查询 adapter 抽象。"""

    @abstractmethod
    def list_tickets(self, scenario_id: str) -> list[TicketRecord]:
        """读取指定场景的工单记录。"""


class RunbookAdapter(ABC):
    """Runbook 查询 adapter 抽象。"""

    @abstractmethod
    def get_runbook(self, scenario_id: str) -> RunbookRecord:
        """读取指定场景的 Runbook 文档。"""


class CMDBAdapter(ABC):
    """CMDB 查询 adapter 抽象。"""

    @abstractmethod
    def get_service(self, scenario_id: str) -> CMDBRecord:
        """读取指定场景的 CMDB 记录。"""
