# Mock 数据格式说明

## 标准目录结构

每个场景必须位于：

`data/mock/scenarios/<scenario_id>/`

每个场景目录必须包含以下文件：

- `alerts.json`：告警列表，JSON 数组。
- `logs.jsonl`：日志流，JSON Lines。
- `metrics.csv`：指标点列表，CSV。
- `changes.json`：变更记录，JSON 数组。
- `tickets.json`：工单记录，JSON 数组。
- `cmdb.json`：CMDB 记录，JSON 数组，当前约定至少包含 1 条服务记录。
- `runbooks.md`：Runbook 文档，Markdown。

## 字段约定

### `alerts.json`

- `alert_id`：告警唯一标识。
- `scenario_id`：场景标识，必须与目录名一致。
- `service`：告警所属服务。
- `name`：告警名称。
- `severity`：告警级别。
- `status`：告警状态，例如 `firing`。
- `fired_at`：触发时间，使用 ISO 8601。
- `resolved_at`：恢复时间，可为空。
- `summary`：告警摘要。
- `labels`：附加标签对象。

### `logs.jsonl`

每行 1 条 JSON 记录，推荐字段：

- `timestamp`：日志时间，使用 ISO 8601。
- `scenario_id`：场景标识。
- `service`：日志来源服务。
- `instance`：实例名称。
- `level`：日志级别。
- `trace_id`：调用链标识，可为空。
- `message`：日志消息。
- `fields`：结构化字段对象。

### `metrics.csv`

固定表头：

`timestamp,scenario_id,service,metric_name,value,unit,labels`

其中 `labels` 使用逗号分隔的 `key=value` 格式，例如：

`endpoint=POST /api/orders,status=500`

### `changes.json`

- `change_id`：变更唯一标识。
- `scenario_id`：场景标识。
- `service`：受影响服务。
- `change_type`：变更类型，例如 `release` 或 `config`。
- `changed_at`：变更时间。
- `operator`：执行人。
- `version`：版本号，可为空。
- `summary`：变更摘要。
- `details`：结构化详情对象。

### `tickets.json`

- `ticket_id`：工单唯一标识。
- `scenario_id`：场景标识。
- `title`：工单标题。
- `status`：工单状态。
- `priority`：工单优先级。
- `created_at`：创建时间。
- `updated_at`：更新时间。
- `owner_team`：责任团队。
- `description`：工单描述。

### `cmdb.json`

- `service`：服务名称。
- `scenario_id`：场景标识。
- `owner_team`：归属团队。
- `environment`：运行环境。
- `repository`：仓库地址。
- `upstreams`：上游依赖列表。
- `downstreams`：下游依赖列表。
- `oncall_team`：值班团队。
- `notes`：补充说明，可为空。

### `runbooks.md`

约定第一行使用一级标题，第二行可包含：

`service: <service_name>`

adapter 会从这里提取 Runbook 标题和服务名。

## 语义一致性要求

- 同一场景下所有文件的 `scenario_id` 必须一致。
- 告警时间、变更时间、日志时间和指标时间必须能拼出清晰时间线。
- 至少要让日志、指标、变更、工单和 Runbook 共同支持一个明确的排障方向。
- `order_api_500_after_release` 需要体现“发布后 500 激增”的时间相关性。
- `payment_timeout_db_saturation` 需要体现“支付超时由数据库资源饱和触发”的因果链。

## 验证方法

运行以下命令：

```powershell
pytest tests/test_mock_adapters.py
```

如果需要手动检查某个场景目录是否完整，可以确认目录下是否存在全部 7 个标准文件，并使用 `MockScenarioRepository.list_scenarios()` 查看已发现的场景列表。
