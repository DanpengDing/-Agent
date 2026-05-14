# Spec: Agent Task Memory Continuity

## Objective
为当前多智能体项目设计并实现一套“任务连续性优先”的记忆系统，重点解决以下问题：

- 人工审批后，任务能够从原阶段继续，而不是像全新问题一样重新开始
- 工具调用失败后，系统能够记住失败位置、失败原因和下一步恢复建议
- 自动重试后，任务目标、执行阶段和关键上下文不丢失
- 用户在同一 session 中用“继续”“那就查一下”“换个办法”这类表达时，系统能够恢复活跃任务

目标用户：

- 使用对话式 Agent 完成维修站查询、技术排障、知识库问答等多步任务的终端用户
- 需要维护和调试多智能体链路的研发人员

成功标准：

- 在审批、工具失败、自动重试、恢复追问场景下，任务状态连续性可观察、可恢复、可测试
- 记忆体系从“短期记忆 + 长期记忆 + 用户偏好”升级为“短期记忆 + 长期记忆 + 用户偏好 + 任务状态记忆”
- 产出达到可在简历中表述为“面向多轮任务恢复的 Agent 记忆系统”的工程完成度

## Tech Stack
- Python 3.10
- FastAPI
- OpenAI Agents SDK
- MySQL / PyMySQL / DBUtils PooledDB
- Pydantic v2
- Vue 3 + Vite + Element Plus
- 本地文件会话存储（现有 session 文件机制）

## Commands
后端开发：

```bash
uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8000
```

前端开发：

```bash
cd front/agent_web_ui
npm run dev
```

前端构建：

```bash
cd front/agent_web_ui
npm run build
```

后端测试：

```bash
python -m pytest backend/app/tests -q
```

记忆相关测试：

```bash
python -m pytest backend/app/tests/test_memory_service.py backend/app/tests/test_agent_service_memory_integration.py backend/app/tests/test_session_service_summary_memory.py backend/app/tests/test_memory_api.py -q
```

## Project Structure
本次 spec 主要涉及以下目录：

```text
backend/app/api/                     → FastAPI 路由层
backend/app/services/                → 业务服务层（Agent、Session、Memory、压缩等）
backend/app/repositories/            → 数据访问层
backend/app/schemas/                 → 请求/响应/会话状态模型
backend/app/tests/                   → 单元测试与集成测试
front/agent_web_ui/src/views/        → 页面级前端视图
front/agent_web_ui/src/api/          → 前端接口封装
docs/superpowers/specs/              → 规格文档
docs/superpowers/plans/              → 实现计划文档
```

任务连续性记忆新增的核心边界：

- `session_service` 继续负责短期会话记忆
- `memory_service` 继续负责长期记忆与用户偏好
- 新增 `task_memory_service` 负责任务状态记忆的创建、更新、恢复和归档
- 新增 `task_memory_repository` 负责任务状态持久化
- `agent_service` 负责把“任务恢复逻辑”接入现有 orchestrator 执行入口

## Code Style
遵循当前项目已有风格：

- 服务层负责业务语义，仓储层负责持久化
- 所有运行时关键链路都要有明确日志
- 失败不能阻断主流程时，要降级并保留可诊断信息
- 测试优先覆盖行为和状态转移，而不是只测工具函数

示例风格：

```python
def build_runtime_history(
    self,
    state: SessionMemoryState,
    user_input: Optional[str] = None,
    append_user_message: bool = True,
) -> List[Dict[str, str]]:
    runtime_history = list(state.system_messages)
    if state.summary is not None:
        runtime_history.append(context_compression_service.format_summary_message(state.summary))
    runtime_history.extend(state.messages)
    if append_user_message and user_input:
        runtime_history.append({"role": "user", "content": user_input})
    return runtime_history
```

本次新增代码约束：

- 任务状态必须结构化，不能只存自然语言长文本
- 任务恢复逻辑必须显式、可测试，不依赖模型“自行理解历史”
- 前端管理能力以查看为主，必要时再做编辑

## Testing Strategy
测试目标是证明“任务连续性”真的成立，而不是只证明表能插入数据。

测试分层：

1. 单元测试
- 任务状态创建
- 任务状态更新
- 活跃任务匹配
- 审批状态转移
- 失败状态转移
- 任务恢复提示构造

2. 集成测试
- `/api/query` 进入审批后创建任务状态
- `/api/human_approval` 恢复后沿用原任务状态
- 工具失败后再次请求会命中原活跃任务
- 自动重试后任务状态仍保留原阶段与重试次数

3. 接口测试
- 查询活跃任务
- 查询任务历史
- 查询长期记忆
- 查询用户偏好
- 管理用户偏好

4. 前端验证
- 记忆管理页能查看长期记忆与偏好
- 新增任务状态相关页面或信息区后能正确展示
- 前端构建必须通过

## Boundaries
- Always:
  - 为任务状态表、服务层和恢复逻辑补测试
  - 所有状态转移都记录日志
  - 任务恢复优先基于结构化状态，而不是依赖聊天全文
  - 任务完成、取消、阻塞后都要正确归档
- Ask first:
  - 改动现有 session 存储机制
  - 新增第三方依赖
  - 将长期记忆/偏好从 MySQL 改为向量库或 Redis
  - 改动前端主导航信息架构超过“增加一个入口”
- Never:
  - 把任务状态和长期记忆混成同一张无结构表
  - 只靠 prompt 文本描述任务恢复，不落结构化状态
  - 为了“更智能”而删除现有可用测试
  - 把用户敏感信息无约束写入日志

## Success Criteria
1. 新增任务状态记忆层，可持久化以下信息：
- task_id
- task_type
- task_goal
- task_status
- task_stage
- structured_context_json
- last_tool_name
- last_tool_result_json
- last_error
- waiting_approval_token
- retry_count
- last_active_at

2. 请求进入时，系统可以识别并恢复当前 session 下的活跃任务：
- `active`
- `waiting_approval`
- `blocked`
- `retrying`

3. 审批恢复时，系统不是“重新开始一轮对话”，而是从原任务阶段继续执行

4. 工具失败后，系统能记住：
- 失败发生在哪个阶段
- 最近一个工具是什么
- 错误原因是什么
- 下一轮继续时应该如何恢复

5. 自动重试时，系统能累加 `retry_count`，并保持原任务目标与上下文不变

6. 长期记忆与用户偏好保留现有能力，不因任务状态记忆的引入而退化

7. 至少新增以下后端能力：
- 查询当前活跃任务
- 查询任务状态列表 / 历史
- 从任务状态构建恢复上下文

8. 至少新增以下前端能力之一：
- 记忆管理页增加任务状态查看区
- 单独的任务记忆页

## Design

### 1. Memory Architecture
系统记忆分为四层：

1. 短期记忆
- 当前 session 内的 messages 与 summary
- 继续使用 `SessionMemoryState`

2. 长期记忆
- 用户长期稳定事实
- 例如常住地、设备信息、长期问题背景

3. 用户偏好
- 用户表达的稳定倾向
- 例如回答简洁、优先推荐官方维修站

4. 任务状态记忆
- 当前任务是什么
- 当前执行到哪一步
- 最近一次工具结果是什么
- 最近一次失败发生在哪
- 是否等待审批
- 下一步恢复建议是什么

其中第四层是本次设计的核心。

### 2. Task Memory Model
新增 `user_task_memory` 表，专门保存任务状态，不与长期记忆混用。

建议字段：

- `id`
- `user_id`
- `session_id`
- `task_id`
- `task_type`
- `task_goal`
- `task_status`
- `task_stage`
- `task_summary`
- `structured_context_json`
- `last_tool_name`
- `last_tool_result_json`
- `last_error`
- `waiting_approval_token`
- `retry_count`
- `priority`
- `created_at`
- `updated_at`
- `last_active_at`
- `closed_at`

状态定义：

- `active`
- `waiting_approval`
- `blocked`
- `retrying`
- `completed`
- `cancelled`

阶段定义按具体任务类型细分，例如：

- `intent_routed`
- `location_resolving`
- `service_station_querying`
- `waiting_human_approval`
- `diagnosis_running`
- `retrying`
- `finished`

### 3. Runtime Flow
每次请求进入主链路时，先走任务恢复，再走 Agent：

1. 加载短期记忆
2. 查找当前 session 下是否存在活跃任务
3. 判断用户输入是否是在继续当前任务
4. 若命中，则构造任务恢复上下文并注入 orchestrator
5. Agent 执行过程中，关键节点更新任务状态
6. 审批中断时，把任务置为 `waiting_approval`
7. 审批恢复时，从原任务阶段继续
8. 工具失败时，把任务置为 `blocked` 或 `retrying`
9. 成功完成后归档为 `completed`

### 4. Recovery Strategy
恢复优先级规则：

- 若存在 `waiting_approval` 任务，优先按审批续跑恢复
- 若存在 `active / blocked / retrying` 任务，且用户输入为继续类表达，则优先恢复
- 若用户输入显式切换新任务，则关闭旧任务或降级旧任务优先级

继续类表达包括但不限于：

- 继续
- 那就查一下
- 我同意
- 换个办法
- 那你再试试
- 重新查附近的

恢复上下文必须包含：

- 当前任务目标
- 当前任务阶段
- 最近工具结果
- 最近失败原因
- 下一步建议动作

### 5. Integration with Existing Memory
任务状态记忆与现有记忆层协同方式如下：

- 短期记忆：保留全部对话上下文
- 长期记忆：沉淀稳定事实
- 用户偏好：沉淀偏好规则
- 任务状态记忆：主导“当前未完成任务”的恢复

任务完成后：

- 可沉淀事实写入长期记忆
- 可沉淀偏好写入用户偏好
- 任务状态归档，不再作为活跃任务恢复

### 6. API Surface
新增后端接口：

- `GET /api/memories/tasks/active?user_id=...&session_id=...`
- `GET /api/memories/tasks?user_id=...&session_id=...`
- `GET /api/memories/tasks/{task_id}?user_id=...`

现有接口保持兼容：

- `/api/query`
- `/api/human_approval`
- `/api/memories/long-term`
- `/api/memories/preferences`

前端最小可见性要求：

- 在“记忆管理”页中增加任务状态查看区
- 至少能看见任务类型、任务状态、当前阶段、最近错误、最近活跃时间

## Open Questions
- 是否需要支持“跨 session 恢复未完成任务”，还是先限定在同一 session 内恢复
- 是否需要在前端提供“手动关闭任务”能力
- 技术专家、服务站查询、知识库问答三类任务是否统一用一套 stage 枚举，还是各自扩展
