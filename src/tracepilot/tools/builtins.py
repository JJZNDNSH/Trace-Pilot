"""TracePilot 内置工具定义。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

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
    TicketAdapter,
)
from tracepilot.domain.enums import ActionRiskLevel
from tracepilot.tools.models import (
    ClearCacheInput,
    DisableFeatureFlagInput,
    GetIncidentTimelineInput,
    GetRecentChangesInput,
    GetServiceDependenciesInput,
    QueryMetricsInput,
    RestartServiceInput,
    RerunHealthCheckInput,
    RollbackReleaseInput,
    SearchAlertsInput,
    SearchLogsInput,
    SearchRunbooksInput,
    SearchTicketsInput,
)
from tracepilot.tools.registry import ToolDefinition, ToolRegistry


@dataclass(slots=True)
class ToolAdapterBundle:
    """工具层 adapter 依赖集合。"""

    # 告警 adapter，用于读取告警类 mock 数据。
    alert_adapter: AlertAdapter
    # 日志 adapter，用于读取日志类 mock 数据。
    log_adapter: LogAdapter
    # 指标 adapter，用于读取指标类 mock 数据。
    metrics_adapter: MetricsAdapter
    # 变更 adapter，用于读取变更类 mock 数据。
    change_adapter: ChangeAdapter
    # 工单 adapter，用于读取工单类 mock 数据。
    ticket_adapter: TicketAdapter
    # Runbook adapter，用于读取 Runbook 文档。
    runbook_adapter: RunbookAdapter
    # CMDB adapter，用于读取服务依赖和拓扑信息。
    cmdb_adapter: CMDBAdapter


class BuiltinToolFactory:
    """内置工具工厂。"""

    # 初始化工厂依赖，用于让工具处理函数复用同一组 adapter 和运行配置。
    def __init__(
        self,
        adapters: ToolAdapterBundle,
        *,
        query_timeout_seconds: float = 1.0,
        execution_timeout_seconds: float = 1.0,
        query_cache_ttl_seconds: int = 30,
    ) -> None:
        self._adapters = adapters
        self._query_timeout_seconds = query_timeout_seconds
        self._execution_timeout_seconds = execution_timeout_seconds
        self._query_cache_ttl_seconds = query_cache_ttl_seconds

    # 构建全部内置工具定义，用于一次性注册模块 3 的工具集合。
    def build_definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="search_alerts",
                description="按场景与条件检索告警记录。",
                risk_level=ActionRiskLevel.AUTO,
                input_model=SearchAlertsInput,
                handler=self._search_alerts,
                fallback_handler=self._query_fallback,
                timeout_seconds=self._query_timeout_seconds,
                cache_enabled=True,
                cache_ttl_seconds=self._query_cache_ttl_seconds,
            ),
            ToolDefinition(
                name="search_logs",
                description="按场景与条件检索日志记录。",
                risk_level=ActionRiskLevel.AUTO,
                input_model=SearchLogsInput,
                handler=self._search_logs,
                fallback_handler=self._query_fallback,
                timeout_seconds=self._query_timeout_seconds,
                cache_enabled=True,
                cache_ttl_seconds=self._query_cache_ttl_seconds,
            ),
            ToolDefinition(
                name="query_metrics",
                description="按场景与条件查询指标点。",
                risk_level=ActionRiskLevel.AUTO,
                input_model=QueryMetricsInput,
                handler=self._query_metrics,
                fallback_handler=self._query_fallback,
                timeout_seconds=self._query_timeout_seconds,
                cache_enabled=True,
                cache_ttl_seconds=self._query_cache_ttl_seconds,
            ),
            ToolDefinition(
                name="get_recent_changes",
                description="读取场景内最近变更记录。",
                risk_level=ActionRiskLevel.AUTO,
                input_model=GetRecentChangesInput,
                handler=self._get_recent_changes,
                fallback_handler=self._query_fallback,
                timeout_seconds=self._query_timeout_seconds,
                cache_enabled=True,
                cache_ttl_seconds=self._query_cache_ttl_seconds,
            ),
            ToolDefinition(
                name="search_tickets",
                description="按条件检索场景工单。",
                risk_level=ActionRiskLevel.AUTO,
                input_model=SearchTicketsInput,
                handler=self._search_tickets,
                fallback_handler=self._query_fallback,
                timeout_seconds=self._query_timeout_seconds,
                cache_enabled=True,
                cache_ttl_seconds=self._query_cache_ttl_seconds,
            ),
            ToolDefinition(
                name="get_service_dependencies",
                description="读取服务依赖拓扑与责任信息。",
                risk_level=ActionRiskLevel.AUTO,
                input_model=GetServiceDependenciesInput,
                handler=self._get_service_dependencies,
                fallback_handler=self._query_fallback,
                timeout_seconds=self._query_timeout_seconds,
                cache_enabled=True,
                cache_ttl_seconds=self._query_cache_ttl_seconds,
            ),
            ToolDefinition(
                name="search_runbooks",
                description="按关键字检索场景 Runbook。",
                risk_level=ActionRiskLevel.AUTO,
                input_model=SearchRunbooksInput,
                handler=self._search_runbooks,
                fallback_handler=self._query_fallback,
                timeout_seconds=self._query_timeout_seconds,
                cache_enabled=True,
                cache_ttl_seconds=self._query_cache_ttl_seconds,
            ),
            ToolDefinition(
                name="get_incident_timeline",
                description="聚合告警、日志、变更和工单时间线。",
                risk_level=ActionRiskLevel.AUTO,
                input_model=GetIncidentTimelineInput,
                handler=self._get_incident_timeline,
                fallback_handler=self._query_fallback,
                timeout_seconds=self._query_timeout_seconds,
                cache_enabled=True,
                cache_ttl_seconds=self._query_cache_ttl_seconds,
            ),
            ToolDefinition(
                name="restart_service",
                description="返回服务重启的 guarded mock 执行计划。",
                risk_level=ActionRiskLevel.GUARDED,
                input_model=RestartServiceInput,
                handler=self._restart_service,
                timeout_seconds=self._execution_timeout_seconds,
            ),
            ToolDefinition(
                name="rollback_release",
                description="返回版本回滚的 guarded mock 执行计划。",
                risk_level=ActionRiskLevel.GUARDED,
                input_model=RollbackReleaseInput,
                handler=self._rollback_release,
                timeout_seconds=self._execution_timeout_seconds,
            ),
            ToolDefinition(
                name="clear_cache",
                description="返回清缓存的 guarded mock 执行计划。",
                risk_level=ActionRiskLevel.GUARDED,
                input_model=ClearCacheInput,
                handler=self._clear_cache,
                timeout_seconds=self._execution_timeout_seconds,
            ),
            ToolDefinition(
                name="disable_feature_flag",
                description="返回关闭特性开关的 guarded mock 执行计划。",
                risk_level=ActionRiskLevel.GUARDED,
                input_model=DisableFeatureFlagInput,
                handler=self._disable_feature_flag,
                timeout_seconds=self._execution_timeout_seconds,
            ),
            ToolDefinition(
                name="rerun_health_check",
                description="返回自动重跑健康检查的 mock 结果。",
                risk_level=ActionRiskLevel.AUTO,
                input_model=RerunHealthCheckInput,
                handler=self._rerun_health_check,
                timeout_seconds=self._execution_timeout_seconds,
            ),
        ]

    # 检索告警并按条件过滤，用于让排障链路快速拿到告警证据。
    def _search_alerts(self, tool_input: BaseModel) -> dict[str, Any]:
        request = SearchAlertsInput.model_validate(tool_input.model_dump())
        alerts = self._adapters.alert_adapter.list_alerts(request.scenario_id)
        filtered = [
            alert
            for alert in alerts
            if self._match_optional_value(request.service, alert.service)
            and self._match_optional_value(request.severity, alert.severity)
            and self._match_optional_value(request.status, alert.status)
            and self._match_keyword(
                request.keyword,
                alert.name,
                alert.summary,
            )
        ]
        items = [alert.model_dump(mode="json") for alert in filtered[: request.limit]]
        return self._build_list_payload(
            scenario_id=request.scenario_id,
            items=items,
            filters=request.model_dump(exclude_none=True),
        )

    # 检索日志并按常见排障条件过滤，用于聚焦关键错误模式。
    def _search_logs(self, tool_input: BaseModel) -> dict[str, Any]:
        request = SearchLogsInput.model_validate(tool_input.model_dump())
        logs = self._adapters.log_adapter.list_logs(request.scenario_id)
        filtered = [
            log
            for log in logs
            if self._match_optional_value(request.service, log.service)
            and self._match_optional_value(request.level, log.level)
            and self._match_optional_value(request.trace_id, log.trace_id)
            and self._match_keyword(request.keyword, log.message)
        ]
        items = [log.model_dump(mode="json") for log in filtered[: request.limit]]
        return self._build_list_payload(
            scenario_id=request.scenario_id,
            items=items,
            filters=request.model_dump(exclude_none=True),
        )

    # 检索指标并支持标签过滤，用于验证错误率、延迟和资源趋势。
    def _query_metrics(self, tool_input: BaseModel) -> dict[str, Any]:
        request = QueryMetricsInput.model_validate(tool_input.model_dump())
        metrics = self._adapters.metrics_adapter.list_metrics(request.scenario_id)
        filtered = [
            metric
            for metric in metrics
            if self._match_optional_value(request.service, metric.service)
            and self._match_optional_value(request.metric_name, metric.metric_name)
            and self._match_labels(request.label_filters, metric.labels)
        ]
        items = [metric.model_dump(mode="json") for metric in filtered[: request.limit]]
        return self._build_list_payload(
            scenario_id=request.scenario_id,
            items=items,
            filters=request.model_dump(exclude_none=True),
        )

    # 检索变更记录并按时间倒序返回，用于建立变更和故障的关联关系。
    def _get_recent_changes(self, tool_input: BaseModel) -> dict[str, Any]:
        request = GetRecentChangesInput.model_validate(tool_input.model_dump())
        changes = self._adapters.change_adapter.list_changes(request.scenario_id)
        filtered = [
            change
            for change in changes
            if self._match_optional_value(request.service, change.service)
            and self._match_optional_value(request.change_type, change.change_type)
        ]
        ordered = sorted(filtered, key=lambda item: item.changed_at, reverse=True)
        items = [change.model_dump(mode="json") for change in ordered[: request.limit]]
        return self._build_list_payload(
            scenario_id=request.scenario_id,
            items=items,
            filters=request.model_dump(exclude_none=True),
        )

    # 检索工单并支持状态、优先级和关键字过滤，用于补充人工处置上下文。
    def _search_tickets(self, tool_input: BaseModel) -> dict[str, Any]:
        request = SearchTicketsInput.model_validate(tool_input.model_dump())
        tickets = self._adapters.ticket_adapter.list_tickets(request.scenario_id)
        filtered = [
            ticket
            for ticket in tickets
            if self._match_optional_value(request.status, ticket.status)
            and self._match_optional_value(request.priority, ticket.priority)
            and self._match_keyword(request.keyword, ticket.title, ticket.description)
        ]
        items = [ticket.model_dump(mode="json") for ticket in filtered[: request.limit]]
        return self._build_list_payload(
            scenario_id=request.scenario_id,
            items=items,
            filters=request.model_dump(exclude_none=True),
        )

    # 返回服务依赖拓扑，用于支持依赖故障和影响范围分析。
    def _get_service_dependencies(self, tool_input: BaseModel) -> dict[str, Any]:
        request = GetServiceDependenciesInput.model_validate(tool_input.model_dump())
        cmdb_record = self._adapters.cmdb_adapter.get_service(request.scenario_id)
        return {
            "scenario_id": request.scenario_id,
            "service": cmdb_record.service,
            "owner_team": cmdb_record.owner_team,
            "environment": cmdb_record.environment,
            "repository": cmdb_record.repository,
            "upstreams": cmdb_record.upstreams,
            "downstreams": cmdb_record.downstreams,
            "oncall_team": cmdb_record.oncall_team,
            "notes": cmdb_record.notes,
        }

    # 检索 Runbook 标题和正文，用于给排障链路补充操作知识。
    def _search_runbooks(self, tool_input: BaseModel) -> dict[str, Any]:
        request = SearchRunbooksInput.model_validate(tool_input.model_dump())
        runbook = self._adapters.runbook_adapter.get_runbook(request.scenario_id)
        matches_service = self._match_optional_value(request.service, runbook.service)
        matches_keyword = self._match_keyword(request.keyword, runbook.title, runbook.content)
        items: list[dict[str, Any]] = []
        if matches_service and matches_keyword:
            items.append(
                {
                    "scenario_id": request.scenario_id,
                    "title": runbook.title,
                    "service": runbook.service,
                    "excerpt": self._build_excerpt(runbook.content, request.keyword),
                    "content": runbook.content,
                }
            )
        return self._build_list_payload(
            scenario_id=request.scenario_id,
            items=items,
            filters=request.model_dump(exclude_none=True),
        )

    # 聚合多源事件为统一时间线，用于帮助排障流程快速恢复“先发生了什么”。
    def _get_incident_timeline(self, tool_input: BaseModel) -> dict[str, Any]:
        request = GetIncidentTimelineInput.model_validate(tool_input.model_dump())
        events: list[dict[str, Any]] = []

        # 先汇总变更和告警事件，便于直接观察故障与发布窗口的时间关系。
        if request.include_changes:
            changes = self._adapters.change_adapter.list_changes(request.scenario_id)
            for change in changes:
                if not self._match_optional_value(request.service, change.service):
                    continue
                events.append(
                    {
                        "timestamp": change.changed_at,
                        "source_type": "change",
                        "summary": change.summary,
                        "detail": change.model_dump(mode="json"),
                    }
                )

        # 告警事件通常是人工注意到问题的起点，因此也纳入统一时间线。
        if request.include_alerts:
            alerts = self._adapters.alert_adapter.list_alerts(request.scenario_id)
            for alert in alerts:
                if not self._match_optional_value(request.service, alert.service):
                    continue
                events.append(
                    {
                        "timestamp": alert.fired_at,
                        "source_type": "alert",
                        "summary": alert.summary,
                        "detail": alert.model_dump(mode="json"),
                    }
                )

        # 日志事件只保留 WARN 和 ERROR，避免时间线被 INFO 噪音淹没。
        if request.include_logs:
            logs = self._adapters.log_adapter.list_logs(request.scenario_id)
            for log in logs:
                if not self._match_optional_value(request.service, log.service):
                    continue
                if log.level.upper() not in {"WARN", "ERROR"}:
                    continue
                events.append(
                    {
                        "timestamp": log.timestamp,
                        "source_type": "log",
                        "summary": log.message,
                        "detail": log.model_dump(mode="json"),
                    }
                )

        # 工单事件用于补充人工介入时间点，便于后续生成交接和复盘摘要。
        if request.include_tickets:
            tickets = self._adapters.ticket_adapter.list_tickets(request.scenario_id)
            for ticket in tickets:
                events.append(
                    {
                        "timestamp": ticket.created_at,
                        "source_type": "ticket",
                        "summary": ticket.title,
                        "detail": ticket.model_dump(mode="json"),
                    }
                )

        ordered = sorted(events, key=lambda item: item["timestamp"])
        items = ordered[: request.limit]
        return self._build_list_payload(
            scenario_id=request.scenario_id,
            items=items,
            filters=request.model_dump(exclude_none=True),
        )

    # 返回 guarded 的 mock 重启计划，用于验证高风险动作不会自动放行。
    def _restart_service(self, tool_input: BaseModel) -> dict[str, Any]:
        request = RestartServiceInput.model_validate(tool_input.model_dump())
        return {
            "execution_mode": "mock",
            "action": "restart_service",
            "service": request.service,
            "environment": request.environment,
            "reason": request.reason,
            "approved": False,
            "plan_steps": [
                "确认当前实例健康状态与流量影响范围。",
                "准备受控重启目标服务实例。",
                "重启后观察错误率和健康检查恢复情况。",
            ],
            "mock_result_preview": f"服务 {request.service} 将在 {request.environment} 环境执行受控重启。",
        }

    # 返回 guarded 的 mock 回滚计划，用于验证发布回归动作会被审批拦截。
    def _rollback_release(self, tool_input: BaseModel) -> dict[str, Any]:
        request = RollbackReleaseInput.model_validate(tool_input.model_dump())
        return {
            "execution_mode": "mock",
            "action": "rollback_release",
            "service": request.service,
            "environment": request.environment,
            "target_version": request.target_version,
            "reason": request.reason,
            "approved": False,
            "plan_steps": [
                "确认当前故障与最近版本变更的相关性。",
                "准备回滚到上一个稳定版本。",
                "回滚后重新观察错误率、延迟和用户影响。",
            ],
            "mock_result_preview": (
                f"服务 {request.service} 将在 {request.environment} 环境回滚到 "
                f"{request.target_version or '上一稳定版本'}。"
            ),
        }

    # 返回 guarded 的 mock 清缓存计划，用于验证风险动作只返回计划不直接执行。
    def _clear_cache(self, tool_input: BaseModel) -> dict[str, Any]:
        request = ClearCacheInput.model_validate(tool_input.model_dump())
        return {
            "execution_mode": "mock",
            "action": "clear_cache",
            "service": request.service,
            "environment": request.environment,
            "cache_name": request.cache_name,
            "reason": request.reason,
            "approved": False,
            "plan_steps": [
                "确认缓存内容与故障现象的关联性。",
                "评估清缓存可能带来的流量抖动和回源压力。",
                "在受控窗口内执行缓存清理并观察恢复情况。",
            ],
            "mock_result_preview": (
                f"服务 {request.service} 将在 {request.environment} 环境清理缓存 {request.cache_name}。"
            ),
        }

    # 返回 guarded 的 mock 特性开关关闭计划，用于验证高风险动作统一治理。
    def _disable_feature_flag(self, tool_input: BaseModel) -> dict[str, Any]:
        request = DisableFeatureFlagInput.model_validate(tool_input.model_dump())
        return {
            "execution_mode": "mock",
            "action": "disable_feature_flag",
            "service": request.service,
            "environment": request.environment,
            "feature_flag": request.feature_flag,
            "reason": request.reason,
            "approved": False,
            "plan_steps": [
                "确认特性开关和当前故障现象是否强相关。",
                "评估关闭开关对用户路径和依赖方的影响。",
                "关闭后重新观察错误率、延迟和业务恢复情况。",
            ],
            "mock_result_preview": (
                f"服务 {request.service} 将在 {request.environment} 环境关闭特性开关 {request.feature_flag}。"
            ),
        }

    # 返回 auto 的 mock 健康检查结果，用于验证低风险执行类工具可以直接返回结果。
    def _rerun_health_check(self, tool_input: BaseModel) -> dict[str, Any]:
        request = RerunHealthCheckInput.model_validate(tool_input.model_dump())
        return {
            "execution_mode": "mock",
            "action": "rerun_health_check",
            "service": request.service,
            "environment": request.environment,
            "check_name": request.check_name,
            "reason": request.reason,
            "simulated": True,
            "result": "healthy",
            "message": f"已在 {request.environment} 环境模拟重跑 {request.service} 的健康检查。",
        }

    # 构建查询类 fallback 结果，用于异常时仍返回可解释的统一结构。
    def _query_fallback(self, tool_input: BaseModel, exc: Exception) -> dict[str, Any]:
        payload = tool_input.model_dump(mode="json")
        return {
            "scenario_id": payload.get("scenario_id"),
            "items": [],
            "count": 0,
            "filters": payload,
            "fallback_reason": str(exc),
        }

    # 构建统一列表型返回结构，用于让查询工具输出格式保持一致。
    def _build_list_payload(
        self,
        *,
        scenario_id: str,
        items: list[dict[str, Any]],
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "scenario_id": scenario_id,
            "items": items,
            "count": len(items),
            "filters": filters,
        }

    # 对可选字段做大小写无关匹配，用于避免调用方自己处理大小写差异。
    def _match_optional_value(self, expected: str | None, actual: str | None) -> bool:
        if expected is None:
            return True
        if actual is None:
            return False
        return expected.lower() == actual.lower()

    # 对多段文本做关键字匹配，用于统一告警、日志、工单和 Runbook 的检索逻辑。
    def _match_keyword(self, keyword: str | None, *candidates: str | None) -> bool:
        if keyword is None:
            return True
        normalized_keyword = keyword.lower()
        return any(
            candidate is not None and normalized_keyword in candidate.lower()
            for candidate in candidates
        )

    # 对标签集合做精确匹配，用于让指标过滤结果更可控。
    def _match_labels(self, expected_labels: dict[str, str], actual_labels: dict[str, str]) -> bool:
        for key, value in expected_labels.items():
            if actual_labels.get(key) != value:
                return False
        return True

    # 从 Runbook 正文里截取与关键字相关的片段，用于减少上层重复处理全文。
    def _build_excerpt(self, content: str, keyword: str | None) -> str:
        if keyword is None:
            return content[:200]
        lowered_content = content.lower()
        lowered_keyword = keyword.lower()
        index = lowered_content.find(lowered_keyword)
        if index == -1:
            return content[:200]
        start = max(index - 40, 0)
        end = min(index + len(keyword) + 80, len(content))
        return content[start:end]


# 构建默认 adapter 集合，用于在不显式注入依赖时直接读取内置 mock 数据。
def build_default_tool_adapters() -> ToolAdapterBundle:
    return ToolAdapterBundle(
        alert_adapter=MockAlertAdapter(),
        log_adapter=MockLogAdapter(),
        metrics_adapter=MockMetricsAdapter(),
        change_adapter=MockChangeAdapter(),
        ticket_adapter=MockTicketAdapter(),
        runbook_adapter=MockRunbookAdapter(),
        cmdb_adapter=MockCMDBAdapter(),
    )


# 构建默认工具注册表，用于让测试和后续服务层可以直接复用统一工具集合。
def build_default_tool_registry(
    adapters: ToolAdapterBundle | None = None,
    *,
    query_timeout_seconds: float = 1.0,
    execution_timeout_seconds: float = 1.0,
    query_cache_ttl_seconds: int = 30,
) -> ToolRegistry:
    registry = ToolRegistry()
    factory = BuiltinToolFactory(
        adapters=adapters or build_default_tool_adapters(),
        query_timeout_seconds=query_timeout_seconds,
        execution_timeout_seconds=execution_timeout_seconds,
        query_cache_ttl_seconds=query_cache_ttl_seconds,
    )
    for definition in factory.build_definitions():
        registry.register(definition)
    return registry
