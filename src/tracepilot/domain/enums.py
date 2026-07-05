"""TracePilot 领域枚举定义。"""

from enum import Enum


class FaultType(str, Enum):
    """故障域分类枚举。"""

    API_ERROR = "api_error"
    RELEASE_REGRESSION = "release_regression"
    DEPENDENCY_FAILURE = "dependency_failure"
    JVM_GC = "jvm_gc"
    RESOURCE_SATURATION = "resource_saturation"
    FALSE_ALARM = "false_alarm"
    UNKNOWN = "unknown"


class UrgencyLevel(str, Enum):
    """故障紧急度枚举。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImpactScope(str, Enum):
    """故障影响范围枚举。"""

    SINGLE_SERVICE = "single_service"
    CROSS_SERVICE = "cross_service"
    USER_FACING = "user_facing"
    UNKNOWN = "unknown"


class AgentType(str, Enum):
    """分析 Agent 角色枚举。"""

    TRIAGE = "TriageAgent"
    LOGS = "LogsAgent"
    METRICS = "MetricsAgent"
    CHANGE = "ChangeAgent"
    DEPENDENCY = "DependencyAgent"


class ToolType(str, Enum):
    """工具语义枚举。"""

    LOG_QUERY = "log_query"
    METRICS_QUERY = "metrics_query"
    CHANGE_QUERY = "change_query"
    DEPENDENCY_QUERY = "dependency_query"
    RUNBOOK_LOOKUP = "runbook_lookup"
    HEALTH_CHECK_RETRY = "health_check_retry"
    SERVICE_RESTART = "service_restart"
    RELEASE_ROLLBACK = "release_rollback"
    CACHE_CLEAR = "cache_clear"
    FEATURE_FLAG_DISABLE = "feature_flag_disable"


class ActionRiskLevel(str, Enum):
    """动作风险分级枚举。"""

    AUTO = "auto"
    GUARDED = "guarded"
    DENIED = "denied"


class InvestigationGraphNode(str, Enum):
    """自研 Agent Loop 编排节点枚举。"""

    LOAD_CONTEXT = "load_context"
    CLASSIFY_INCIDENT = "classify_incident"
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    PLAN_INVESTIGATION = "plan_investigation"
    RUN_INVESTIGATION_STEP = "run_investigation_step"
    RUN_LOGS_AGENT = "run_logs_agent"
    RUN_METRICS_AGENT = "run_metrics_agent"
    RUN_CHANGE_AGENT = "run_change_agent"
    RUN_DEPENDENCY_AGENT = "run_dependency_agent"
    MERGE_FINDINGS = "merge_findings"
    COMPRESS_STATE = "compress_state"
    DECIDE_NEXT_STEP = "decide_next_step"
    PREPARE_ACTIONS = "prepare_actions"
    AWAIT_APPROVAL = "await_approval"
    EXECUTE_ACTIONS = "execute_actions"
    GENERATE_RESPONSE = "generate_response"
    GENERATE_HANDOFF = "generate_handoff"


class ToolExecutionStatus(str, Enum):
    """工具结果状态枚举。"""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class InvestigationStatus(str, Enum):
    """排障会话生命周期状态枚举。"""

    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
