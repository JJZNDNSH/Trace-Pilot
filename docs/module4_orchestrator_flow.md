# TracePilot 模块 4 编排执行流程说明

## 1. 当前编排结构

当前模块使用自研 `InvestigationGraphRunner`，不依赖 LangGraph。

执行结构固定为三段：

1. 初始化阶段
   - `load_context`
   - `classify_incident`
   - `retrieve_knowledge`
2. Agent Loop 主循环
   - `plan_investigation`
   - `run_investigation_step`
   - `merge_findings`
   - `compress_state`
   - `decide_next_step`
3. 收口阶段
   - `generate_response`

`decide_next_step` 当前显式支持两条分支：

- `plan_investigation`：继续下一轮 loop
- `generate_response`：结束 loop 并收口输出

## 2. 步骤读写的 state 字段

| 步骤 | 读取字段 | 写入字段 |
| --- | --- | --- |
| `load_context` | `session_id` `environment` `problem_statement` `scenario_id` | `confirmed_facts` `evidence` `stage_summary` `next_steps` `current_node` `loop_count` |
| `classify_incident` | `problem_statement` | `fault_type` `urgency` `impact_scope` `selected_agents` `escalated` `stage_summary` `current_node` |
| `retrieve_knowledge` | `scenario_id` `fault_type` | `knowledge_summary` `confirmed_facts` `stage_summary` `next_steps` `current_node` |
| `plan_investigation` | `fault_type` `knowledge_summary` `loop_count` | `selected_tools` `next_steps` `stage_summary` `current_node` |
| `run_investigation_step` | `scenario_id` `selected_tools` `fault_type` `loop_count` | `investigation_findings` `tool_results` `stage_summary` `current_node` |
| `merge_findings` | `investigation_findings` `fault_type` | `confirmed_facts` `hypotheses` `candidate_actions` `pending_actions` `next_steps` `stage_summary` `current_node` |
| `compress_state` | `confirmed_facts` `hypotheses` `loop_count` | `stage_summary` `stage_summaries` `next_steps` `current_node` |
| `decide_next_step` | `loop_count` `confirmed_facts` `pending_actions` | `loop_count` `should_respond` `next_steps` `stage_summary` `current_node` |
| `generate_response` | `stage_summary` `pending_actions` `confirmed_facts` `hypotheses` `loop_count` | `response_summary` `status` `should_respond` `next_steps` `stage_summary` `current_node` |

本模块重点覆盖了以下状态字段在步骤间的传递：

- `session_id`
- `problem_statement`
- `fault_type`
- `urgency`
- `selected_tools`
- `confirmed_facts`
- `hypotheses`
- `next_steps`
- `stage_summary`
- `loop_count`
- `should_respond`

## 3. Loop 是怎么实现的

`InvestigationGraphRunner.run()` 在初始化阶段之后进入 `while True`：

1. 先执行一轮 `plan_investigation -> run_investigation_step -> merge_findings -> compress_state -> decide_next_step`
2. `decide_next_step` 会递增 `loop_count`
3. 如果 `should_respond=True`，跳出循环并进入 `generate_response`
4. 如果 `should_respond=False`，路由回 `plan_investigation`

当前通过 `DEFAULT_MAX_LOOP_COUNT = 2` 限制最大轮数，防止死循环。

## 4. `/investigate` 如何对接编排器

`InvestigationService.investigate()` 现在只做三件事：

1. 调用 `InvestigationGraphRunner.run(request)`
2. 保存 `execution.state`
3. 基于 `execution.response` 回填 `latency_ms` 并返回

这样 `/investigate` 已经由统一编排入口驱动，而不是手写串行逻辑。

## 5. 后续如何扩展成多 Agent 并行

当前的并行扩展点主要有两个：

1. `plan_investigation`
   - 现在只产出统一 `selected_tools`
   - 后续可在这里改为产出多个专业 Agent 任务清单
2. `run_investigation_step`
   - 当前是统一占位执行点
   - 模块 5 可以拆为 `run_logs_agent`、`run_metrics_agent`、`run_change_agent`、`run_dependency_agent`
   - 多路结果仍然统一进入 `merge_findings`

审批流扩展点在 `InvestigationGraphRunner._route_after_decision()` 旁边已经预留，后续可在 `should_respond` 之外增加 guarded 分支路由。

## 6. 如何验证

运行：

```bash
pytest tests/test_main_graph.py tests/test_api.py
```

重点验证点：

- 编排器可完整执行到 `generate_response`
- `/investigate` 已接入自研编排器入口
- `loop_count` 至少增长到 `2`
- `stage_summaries` 中 `plan_investigation` 至少出现两次
- 标准场景 `order_api_500_after_release` 能完整跑通
