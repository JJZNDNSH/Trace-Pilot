# TracePilot Phase 1 进度记录

## 1. 当前阶段结论
- 当前已完成模块 1：领域模型与 API 契约。
- 当前服务可以启动，Swagger 可以访问，最小接口测试已经通过。
- 当前只实现了接口层、状态骨架和审批占位逻辑。
- 当前未实现真实工具调用、真实 LangGraph 编排、真实 Agent 推理。

## 2. 本阶段完成内容

### 2.1 领域模型与枚举
- 已定义故障域、紧急度、影响范围、Agent 类型、工具类型、动作风险分级、LangGraph 节点枚举。
- 已定义 `InvestigationState`，覆盖 `PLAN.md` 当前要求的核心状态字段。
- 已定义事实、假设、证据、工具结果、阶段摘要、待审批动作、执行结果、审计记录等值对象。

关键文件：
- [src/tracepilot/domain/enums.py](/D:/code/TracePilot/src/tracepilot/domain/enums.py:1)
- [src/tracepilot/domain/models.py](/D:/code/TracePilot/src/tracepilot/domain/models.py:1)
- [src/tracepilot/domain/state.py](/D:/code/TracePilot/src/tracepilot/domain/state.py:27)

### 2.2 API 契约
- 已定义 `POST /investigate` 请求响应模型。
- 已定义 `POST /actions/approve` 请求响应模型。
- 已定义 `GET /health` 响应模型。

关键文件：
- [src/tracepilot/schemas/investigation.py](/D:/code/TracePilot/src/tracepilot/schemas/investigation.py:18)
- [src/tracepilot/schemas/health.py](/D:/code/TracePilot/src/tracepilot/schemas/health.py:6)

### 2.3 FastAPI 路由骨架
- 已实现 `GET /health`
- 已实现 `POST /investigate`
- 已实现 `POST /actions/approve`
- 已完成应用入口和 Swagger 暴露

关键文件：
- [src/tracepilot/api/routes.py](/D:/code/TracePilot/src/tracepilot/api/routes.py:24)
- [src/tracepilot/main.py](/D:/code/TracePilot/src/tracepilot/main.py:10)

### 2.4 服务层骨架
- 已实现最小排障服务骨架。
- 已支持创建会话、生成初始状态、返回待审批动作占位、审批后更新状态。
- 当前审批执行结果为模拟结果，不调用真实执行工具。

关键文件：
- [src/tracepilot/services/investigation_service.py](/D:/code/TracePilot/src/tracepilot/services/investigation_service.py:58)

### 2.5 测试与文档
- 已补充最小接口测试。
- 已补充对外接口文档。

关键文件：
- [tests/test_api.py](/D:/code/TracePilot/tests/test_api.py:13)
- [docs/api_contract.md](/D:/code/TracePilot/docs/api_contract.md:1)

## 3. 当前可用能力

### 3.1 investigate
- 可以接收故障描述并创建 `session_id`
- 可以返回初步 `fault_type`
- 可以返回初步 `urgency`
- 可以返回 `selected_agents`
- 可以返回 `selected_tools`
- 可以返回 `confirmed_facts`
- 可以返回 `hypotheses`
- 可以返回 `next_steps`
- 在发布回归关键词命中时，可以返回 `guarded` 的 `pending_actions`

### 3.2 actions/approve
- 可以根据 `session_id + action_id` 审批待处理动作
- 可以返回 `execution_result`
- 可以返回 `updated_state`
- 可以返回 `audit_record`

### 3.3 health
- 可以用于服务探活

## 4. 已验证结果

### 4.1 本地测试结果
执行命令：

```bash
pytest
```

结果：

```text
4 passed
```

### 4.2 服务启动结果
执行命令：

```bash
python -m uvicorn tracepilot.main:app --app-dir src --reload
```

已确认：
- 服务可启动
- `http://127.0.0.1:8000/docs` 可访问
- `http://127.0.0.1:8000/openapi.json` 可访问
- `http://127.0.0.1:8000/health` 返回正常

说明：
- 浏览器访问 `/` 返回 `404` 属于当前预期，因为本阶段没有实现根路径首页。

## 5. 当前限制
- 当前没有接入 LangGraph `StateGraph`
- 当前没有接入真实 Adapter
- 当前没有读取 `data/mock/scenarios/<scenario_id>/`
- 当前没有实现真实 `load_context / retrieve_knowledge / plan_investigation` 节点
- 当前没有实现多 Agent 并行
- 当前没有实现真实动作执行
- 当前没有接 Skills / Monitor / Eval
- 当前状态存储为内存存储，服务重启后会丢失

## 6. 下一步建议

建议直接进入 Phase 2，并按下面顺序推进。

### 6.1 第一步：搭 LangGraph 主图骨架
- 新建图构建模块
- 定义 `StateGraph[InvestigationState]`
- 先串起以下节点骨架：
  - `load_context`
  - `classify_incident`
  - `retrieve_knowledge`
  - `plan_investigation`
  - `merge_findings`
  - `compress_state`
  - `decide_next_step`
  - `generate_response`
- 节点内部先返回 mock 结果即可

目标：
- 让 `/investigate` 不再直接手写流程，而是走统一图执行入口

### 6.2 第二步：接管 investigate 服务
- 保留当前请求响应模型不变
- 把 [src/tracepilot/services/investigation_service.py](/D:/code/TracePilot/src/tracepilot/services/investigation_service.py:58) 中的手写占位逻辑迁移为：
  - 初始化 `InvestigationState`
  - 调用 LangGraph 主图
  - 从最终状态组装 `InvestigateResponse`

目标：
- 保证后续模块扩展时不重做接口层

### 6.3 第三步：定义 Adapter 抽象与 mock 数据入口
- 先定义：
  - `LogAdapter`
  - `MetricsAdapter`
  - `ChangeAdapter`
  - `DependencyAdapter`
  - `RunbookAdapter`
- 先提供 `Mock*Adapter`
- 按 `PLAN.md` 约定建立 `data/mock/scenarios/<scenario_id>/`

目标：
- 为真实节点提供稳定数据来源

### 6.4 第四步：补充 Phase 2 测试
- 测状态对象在图中流转是否完整
- 测节点返回结构是否稳定
- 测 mock adapter 失败时是否能 fallback
- 测 `scenario_id` 是否能驱动 mock 数据读取

## 7. 推荐的下一步实施任务

如果紧接着继续开发，建议下一条任务写成：

```text
实现 TracePilot 的模块 2：LangGraph 主图骨架与查询工具底座（先用 mock 节点和 mock adapter，不接真实工具）。
```

更细的执行目标建议是：
- 搭建 `StateGraph[InvestigationState]`
- 实现 `load_context -> classify_incident -> retrieve_knowledge -> plan_investigation -> merge_findings -> compress_state -> decide_next_step -> generate_response`
- 保持现有 `/investigate` 和 `/actions/approve` 契约不变
- 增加 Phase 2 最小测试

## 8. 环境与运行命令

### 8.1 Anaconda 创建环境
```bash
conda create -n tracepilot python=3.13 -y
conda activate tracepilot
```

### 8.2 安装依赖
```bash
cd D:\code\TracePilot
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

### 8.3 运行服务
```bash
python -m uvicorn tracepilot.main:app --app-dir src --reload
```

### 8.4 运行测试
```bash
pytest
```
