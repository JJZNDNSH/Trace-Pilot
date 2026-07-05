"""TracePilot 工具注册与运行时底座。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

from pydantic import BaseModel

from tracepilot.domain.enums import ActionRiskLevel
from tracepilot.tools.models import (
    ToolCallStatus,
    ToolGovernanceMarker,
    ToolResponse,
    ToolRuntimeMetadata,
    ToolSpec,
    ToolStatsSnapshot,
)

ToolHandler = Callable[[BaseModel], Any]
FallbackHandler = Callable[[BaseModel, Exception], Any]


@dataclass(slots=True)
class ToolDefinition:
    """单个工具的注册定义。"""

    # 工具名称，用于在注册表里唯一定位一个工具。
    name: str
    # 工具说明，用于帮助调用方快速理解工具职责。
    description: str
    # 风险等级，用于决定工具是自动执行、待审批还是直接拒绝。
    risk_level: ActionRiskLevel
    # 入参模型，用于对工具调用参数做统一校验。
    input_model: type[BaseModel]
    # 主处理函数，用于执行业务逻辑或生成 mock 结果。
    handler: ToolHandler
    # fallback 处理函数，用于异常或超时时返回可解释降级结果。
    fallback_handler: FallbackHandler | None = None
    # 超时时间，用于约束单次工具调用的最长执行时长。
    timeout_seconds: float = 1.0
    # 是否启用缓存，用于让查询类工具复用近期结果。
    cache_enabled: bool = False
    # 缓存 TTL，用于控制缓存结果可复用多久。
    cache_ttl_seconds: int = 0

    # 生成工具说明对象，用于统一暴露注册表里的 schema 信息。
    def to_spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            risk_level=self.risk_level,
            timeout_seconds=self.timeout_seconds,
            cache_enabled=self.cache_enabled,
            cache_ttl_seconds=self.cache_ttl_seconds,
            input_schema=self.input_model.model_json_schema(),
        )


@dataclass(slots=True)
class _ToolCacheEntry:
    """工具缓存条目。"""

    # 缓存的响应对象，用于命中时直接复用结构化返回。
    response: ToolResponse
    # 过期时间戳，用于判断缓存是否仍然有效。
    expires_at: float


@dataclass(slots=True)
class _ToolStatsCounter:
    """单个工具的统计计数器。"""

    # 工具名称，用于生成对外暴露的统计快照。
    tool_name: str
    # 总调用次数，用于统计工具整体被调用频率。
    total_calls: int = 0
    # 成功次数，用于统计稳定返回主结果的调用量。
    success_calls: int = 0
    # fallback 次数，用于统计降级执行的调用量。
    fallback_calls: int = 0
    # 失败次数，用于统计未被 fallback 消化的错误。
    failed_calls: int = 0
    # 超时次数，用于统计耗时超过阈值的调用量。
    timeout_calls: int = 0
    # 缓存命中次数，用于衡量缓存复用效果。
    cache_hits: int = 0
    # guarded 次数，用于统计需要审批的动作被触发多少次。
    guarded_calls: int = 0
    # denied 次数，用于统计被策略拒绝的动作数量。
    denied_calls: int = 0
    # 累计耗时，用于计算平均延迟。
    latency_total_ms: int = 0

    # 记录一次工具调用结果，用于统一沉淀 success、fallback、timeout 等统计。
    def record(
        self,
        *,
        status: ToolCallStatus,
        latency_ms: int,
        from_cache: bool,
        timed_out: bool,
    ) -> None:
        self.total_calls += 1
        self.latency_total_ms += latency_ms
        if status == ToolCallStatus.SUCCESS:
            self.success_calls += 1
        elif status == ToolCallStatus.FALLBACK:
            self.fallback_calls += 1
        elif status == ToolCallStatus.FAILED:
            self.failed_calls += 1
        elif status == ToolCallStatus.GUARDED:
            self.guarded_calls += 1
        elif status == ToolCallStatus.DENIED:
            self.denied_calls += 1
        if from_cache:
            self.cache_hits += 1
        if timed_out:
            self.timeout_calls += 1

    # 输出对外可序列化的统计快照，用于测试和上层流程直接断言。
    def snapshot(self) -> ToolStatsSnapshot:
        average_latency_ms = (
            self.latency_total_ms / self.total_calls if self.total_calls else 0.0
        )
        return ToolStatsSnapshot(
            tool_name=self.tool_name,
            total_calls=self.total_calls,
            success_calls=self.success_calls,
            fallback_calls=self.fallback_calls,
            failed_calls=self.failed_calls,
            timeout_calls=self.timeout_calls,
            cache_hits=self.cache_hits,
            guarded_calls=self.guarded_calls,
            denied_calls=self.denied_calls,
            average_latency_ms=average_latency_ms,
        )


class ToolRegistry:
    """统一工具注册表。"""

    # 初始化注册表，用于统一管理工具定义、缓存和统计数据。
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._cache: dict[str, _ToolCacheEntry] = {}
        self._stats: dict[str, _ToolStatsCounter] = {}

    # 注册单个工具定义，用于为调用方暴露统一入口和 schema。
    def register(self, definition: ToolDefinition) -> None:
        self._definitions[definition.name] = definition
        self._stats.setdefault(definition.name, _ToolStatsCounter(tool_name=definition.name))

    # 列出当前已注册工具，用于输出工具清单和 schema 信息。
    def list_tools(self) -> list[ToolSpec]:
        return [self._definitions[name].to_spec() for name in sorted(self._definitions)]

    # 调用指定工具，并统一处理校验、超时、fallback、缓存和统计。
    def invoke(self, tool_name: str, payload: dict[str, Any]) -> ToolResponse:
        definition = self._get_definition(tool_name)
        request_model = definition.input_model.model_validate(payload)
        cache_key = self._build_cache_key(tool_name, request_model)
        started_at = perf_counter()

        # 对 denied 工具直接做结构化拒绝，避免任何处理函数被误调用。
        if definition.risk_level == ActionRiskLevel.DENIED:
            latency_ms = int((perf_counter() - started_at) * 1000)
            response = self._build_response(
                definition=definition,
                status=ToolCallStatus.DENIED,
                message="当前动作被风险策略拒绝，工具不会执行。",
                data=None,
                error=None,
                latency_ms=latency_ms,
                cache_key=cache_key,
                from_cache=False,
                used_fallback=False,
                timed_out=False,
            )
            self._record_stats(
                tool_name=tool_name,
                status=response.status,
                latency_ms=latency_ms,
                from_cache=False,
                timed_out=False,
            )
            response.stats = self._stats[tool_name].snapshot()
            return response

        # 对启用缓存的查询工具优先尝试命中缓存，减少重复读取 mock 数据。
        cached_response = self._get_cached_response(definition, cache_key)
        if cached_response is not None:
            latency_ms = int((perf_counter() - started_at) * 1000)
            cached_response.runtime.from_cache = True
            cached_response.runtime.latency_ms = latency_ms
            cached_response.runtime.cache_key = cache_key
            self._record_stats(
                tool_name=tool_name,
                status=cached_response.status,
                latency_ms=latency_ms,
                from_cache=True,
                timed_out=False,
            )
            cached_response.stats = self._stats[tool_name].snapshot()
            return cached_response

        try:
            data = self._run_handler(definition, request_model)
            latency_ms = int((perf_counter() - started_at) * 1000)
            status = (
                ToolCallStatus.GUARDED
                if definition.risk_level == ActionRiskLevel.GUARDED
                else ToolCallStatus.SUCCESS
            )
            message = (
                "动作已标记为 guarded，当前阶段仅返回 mock 执行计划。"
                if status == ToolCallStatus.GUARDED
                else "工具执行成功。"
            )
            response = self._build_response(
                definition=definition,
                status=status,
                message=message,
                data=data,
                error=None,
                latency_ms=latency_ms,
                cache_key=cache_key,
                from_cache=False,
                used_fallback=False,
                timed_out=False,
            )
        except FuturesTimeoutError as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            response = self._build_error_response(
                definition=definition,
                request_model=request_model,
                cache_key=cache_key,
                latency_ms=latency_ms,
                exc=exc,
                timed_out=True,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((perf_counter() - started_at) * 1000)
            response = self._build_error_response(
                definition=definition,
                request_model=request_model,
                cache_key=cache_key,
                latency_ms=latency_ms,
                exc=exc,
                timed_out=False,
            )

        self._record_stats(
            tool_name=tool_name,
            status=response.status,
            latency_ms=response.runtime.latency_ms,
            from_cache=response.runtime.from_cache,
            timed_out=response.runtime.timed_out,
        )
        response.stats = self._stats[tool_name].snapshot()

        # 只缓存主成功结果，避免把 fallback 或 guarded 状态固化为陈旧缓存。
        if definition.cache_enabled and response.status == ToolCallStatus.SUCCESS:
            self._cache[cache_key] = _ToolCacheEntry(
                response=response.model_copy(deep=True),
                expires_at=perf_counter() + definition.cache_ttl_seconds,
            )
        return response

    # 返回单个工具的统计快照，用于测试或监控侧读取。
    def get_stats(self, tool_name: str) -> ToolStatsSnapshot:
        definition = self._get_definition(tool_name)
        return self._stats[definition.name].snapshot()

    # 读取工具定义，不存在时抛出显式异常避免静默失败。
    def _get_definition(self, tool_name: str) -> ToolDefinition:
        definition = self._definitions.get(tool_name)
        if definition is None:
            raise KeyError(f"Tool '{tool_name}' is not registered.")
        return definition

    # 在独立线程里运行工具处理函数，用于统一支持同步 handler 的超时控制。
    def _run_handler(self, definition: ToolDefinition, request_model: BaseModel) -> Any:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(definition.handler, request_model)
        try:
            return future.result(timeout=definition.timeout_seconds)
        finally:
            # 超时后不等待后台线程结束，避免调用方明明超时却仍被动卡住。
            executor.shutdown(wait=False, cancel_futures=True)

    # 构建统一响应对象，确保所有工具输出字段结构一致。
    def _build_response(
        self,
        *,
        definition: ToolDefinition,
        status: ToolCallStatus,
        message: str,
        data: Any,
        error: str | None,
        latency_ms: int,
        cache_key: str,
        from_cache: bool,
        used_fallback: bool,
        timed_out: bool,
    ) -> ToolResponse:
        return ToolResponse(
            tool_name=definition.name,
            status=status,
            message=message,
            data=data,
            error=error,
            governance=self._build_governance_marker(definition.risk_level),
            runtime=ToolRuntimeMetadata(
                from_cache=from_cache,
                used_fallback=used_fallback,
                timed_out=timed_out,
                latency_ms=latency_ms,
                cache_key=cache_key,
            ),
            stats=self._stats[definition.name].snapshot(),
        )

    # 在异常场景下优先尝试 fallback，以保证查询链路可解释降级而不是直接中断。
    def _build_error_response(
        self,
        *,
        definition: ToolDefinition,
        request_model: BaseModel,
        cache_key: str,
        latency_ms: int,
        exc: Exception,
        timed_out: bool,
    ) -> ToolResponse:
        if definition.fallback_handler is not None:
            data = definition.fallback_handler(request_model, exc)
            return self._build_response(
                definition=definition,
                status=ToolCallStatus.FALLBACK,
                message=(
                    "工具执行超时，已返回 fallback 结果。"
                    if timed_out
                    else "工具执行异常，已返回 fallback 结果。"
                ),
                data=data,
                error=str(exc),
                latency_ms=latency_ms,
                cache_key=cache_key,
                from_cache=False,
                used_fallback=True,
                timed_out=timed_out,
            )
        return self._build_response(
            definition=definition,
            status=ToolCallStatus.FAILED,
            message=(
                "工具执行超时，且当前工具未配置 fallback。"
                if timed_out
                else "工具执行失败。"
            ),
            data=None,
            error=str(exc),
            latency_ms=latency_ms,
            cache_key=cache_key,
            from_cache=False,
            used_fallback=False,
            timed_out=timed_out,
        )

    # 生成风险治理标记，让 auto、guarded、denied 的结构化差异始终稳定。
    def _build_governance_marker(self, risk_level: ActionRiskLevel) -> ToolGovernanceMarker:
        if risk_level == ActionRiskLevel.GUARDED:
            return ToolGovernanceMarker(
                risk_level=risk_level,
                requires_approval=True,
                denied=False,
                reason="当前动作属于 guarded 级别，需要审批后才能进入真实执行。",
            )
        if risk_level == ActionRiskLevel.DENIED:
            return ToolGovernanceMarker(
                risk_level=risk_level,
                requires_approval=False,
                denied=True,
                reason="当前动作属于 denied 级别，策略禁止执行。",
            )
        return ToolGovernanceMarker(
            risk_level=risk_level,
            requires_approval=False,
            denied=False,
            reason="当前动作属于 auto 级别，可自动执行或自动查询。",
        )

    # 为缓存工具生成稳定缓存键，确保相同输入可以命中同一份结果。
    def _build_cache_key(self, tool_name: str, request_model: BaseModel) -> str:
        payload = request_model.model_dump(mode="json")
        serialized_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return f"{tool_name}:{serialized_payload}"

    # 读取缓存结果并复制响应对象，避免后续运行时字段污染缓存原始值。
    def _get_cached_response(
        self,
        definition: ToolDefinition,
        cache_key: str,
    ) -> ToolResponse | None:
        if not definition.cache_enabled:
            return None
        cache_entry = self._cache.get(cache_key)
        if cache_entry is None:
            return None
        if cache_entry.expires_at <= perf_counter():
            self._cache.pop(cache_key, None)
            return None
        return cache_entry.response.model_copy(deep=True)

    # 统一写入统计结果，确保缓存、fallback、timeout 等数据口径一致。
    def _record_stats(
        self,
        *,
        tool_name: str,
        status: ToolCallStatus,
        latency_ms: int,
        from_cache: bool,
        timed_out: bool,
    ) -> None:
        self._stats[tool_name].record(
            status=status,
            latency_ms=latency_ms,
            from_cache=from_cache,
            timed_out=timed_out,
        )
