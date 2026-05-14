# Implementation Plan: Agent Task Memory Continuity

## Overview
基于现有多智能体系统，新增“任务状态记忆”这一层，使 Agent 在人工审批、工具调用失败、自动重试和恢复追问后，能够从原任务阶段继续执行，而不是重新从头理解整段对话。本计划在不推翻现有短期记忆、长期记忆和用户偏好能力的前提下，补齐任务状态的持久化、恢复、归档、查询和前端可见性。

## Architecture Decisions
- 任务连续性采用独立的 `user_task_memory` 持久化表，而不是复用长期记忆表。这样任务状态、长期事实和用户偏好边界清楚，避免语义污染。
- 任务恢复逻辑放在 `agent_service` 请求主链路里，在 orchestrator 执行前完成“命中活跃任务 → 注入恢复上下文”的处理。
- 服务层新增 `task_memory_service`，仓储层新增 `task_memory_repository`。任务状态的创建、更新、恢复和归档都走独立服务，不把逻辑散落在现有 agent/tool 代码里。
- 先支持同一 `session_id` 内的任务恢复，跨 session 恢复暂不纳入本轮实现，避免范围失控。
- 前端不新增复杂编辑能力，先在“记忆管理”页加入任务状态查看区，提供足够的可观测性和演示能力。

## Task List

### Phase 1: Foundation

## Task 1: 定义任务状态数据模型与仓储接口

**Description:**  
新增任务状态持久化基础设施，包括 MySQL 表结构、仓储读写方法和状态字段约定，为后续的恢复逻辑提供统一数据源。

**Acceptance criteria:**
- [ ] 新增 `user_task_memory` 表定义与自动建表逻辑
- [ ] 仓储层支持创建、更新、查询活跃任务、查询任务列表、按 `task_id` 查询
- [ ] 状态字段覆盖 `active / waiting_approval / blocked / retrying / completed / cancelled`

**Verification:**
- [ ] 测试通过：`python -m pytest backend/app/tests/test_task_memory_repository.py -q`
- [ ] 手工检查：表字段包含 `task_stage`、`structured_context_json`、`last_tool_result_json`、`waiting_approval_token`

**Dependencies:** None

**Files likely touched:**
- `backend/app/repositories/task_memory_repository.py`
- `backend/app/tests/test_task_memory_repository.py`

**Estimated scope:** Medium

## Task 2: 定义任务状态服务层与状态转移规则

**Description:**  
新增 `task_memory_service`，封装任务创建、状态更新、审批挂起、重试标记、完成归档、恢复提示构建等逻辑，避免在主流程中直接操作底层仓储。

**Acceptance criteria:**
- [ ] 新增 `task_memory_service`，提供 create/update/block/waiting_approval/retrying/complete/cancel API
- [ ] 提供“恢复上下文消息”构造方法
- [ ] 提供“继续类输入”识别方法

**Verification:**
- [ ] 测试通过：`python -m pytest backend/app/tests/test_task_memory_service.py -q`
- [ ] 手工检查：服务层不直接依赖前端事件格式，只处理任务状态语义

**Dependencies:** Task 1

**Files likely touched:**
- `backend/app/services/task_memory_service.py`
- `backend/app/tests/test_task_memory_service.py`

**Estimated scope:** Medium

## Checkpoint: Foundation
- [ ] `python -m pytest backend/app/tests/test_task_memory_repository.py backend/app/tests/test_task_memory_service.py -q` 全部通过
- [ ] 仓储层和服务层边界清晰，无主流程耦合
- [ ] `user_task_memory` 可在本地数据库自动创建

### Phase 2: Core Backend Flow

## Task 3: 在主请求链路接入任务恢复前置逻辑

**Description:**  
在 `/api/query` 主链路中加入“加载活跃任务 → 判断是否恢复 → 注入恢复上下文”的前置步骤，使 orchestrator 能基于任务状态执行，而不是只依赖聊天历史。

**Acceptance criteria:**
- [ ] `agent_service.process_task` 在 orchestrator 执行前查询活跃任务
- [ ] 继续类输入会优先命中并恢复当前任务
- [ ] 恢复上下文会插入到运行时 history 中

**Verification:**
- [ ] 测试通过：`python -m pytest backend/app/tests/test_agent_service_task_resume.py -q`
- [ ] 手工检查：未命中活跃任务时，流程与当前行为兼容

**Dependencies:** Task 2

**Files likely touched:**
- `backend/app/services/agent_service.py`
- `backend/app/tests/test_agent_service_task_resume.py`

**Estimated scope:** Medium

## Task 4: 在服务站审批链路接入任务状态更新

**Description:**  
围绕当前最重要的服务站场景，在进入审批、审批恢复、审批拒绝时更新任务状态，确保“等待审批 → 恢复执行”是一条连续任务而不是两次独立对话。

**Acceptance criteria:**
- [ ] 触发审批时创建或更新任务为 `waiting_approval`
- [ ] 审批通过后任务恢复为 `active` 并继续后续阶段
- [ ] 审批拒绝后任务标记为 `cancelled`

**Verification:**
- [ ] 测试通过：`python -m pytest backend/app/tests/test_task_memory_approval_flow.py -q`
- [ ] 手工检查：审批 token 可回写到任务状态

**Dependencies:** Task 3

**Files likely touched:**
- `backend/app/services/agent_service.py`
- `backend/app/api/routers.py`
- `backend/app/tests/test_task_memory_approval_flow.py`

**Estimated scope:** Medium

## Task 5: 在工具失败与自动重试链路接入任务状态更新

**Description:**  
把工具失败、自动重试和最终失败结果写入任务状态，使系统知道“卡在哪”“已经重试过几次”“下一轮恢复时应该怎么继续”。

**Acceptance criteria:**
- [ ] 工具失败时任务状态可更新为 `blocked` 或 `retrying`
- [ ] `retry_count` 会随着自动重试累加
- [ ] 最近失败原因与最近工具结果可写入任务状态

**Verification:**
- [ ] 测试通过：`python -m pytest backend/app/tests/test_task_memory_retry_flow.py -q`
- [ ] 手工检查：失败后再次输入“继续”时可命中原任务

**Dependencies:** Task 3

**Files likely touched:**
- `backend/app/services/agent_service.py`
- `backend/app/multi_agent/agent_factory.py`
- `backend/app/tests/test_task_memory_retry_flow.py`

**Estimated scope:** Medium

## Checkpoint: Core Backend Flow
- [ ] `python -m pytest backend/app/tests/test_agent_service_task_resume.py backend/app/tests/test_task_memory_approval_flow.py backend/app/tests/test_task_memory_retry_flow.py -q` 全部通过
- [ ] 审批恢复、失败重试、继续类输入三条核心链路均能恢复任务
- [ ] 主链路未破坏现有长期记忆、偏好和会话持久化逻辑

### Phase 3: Queryability and Visibility

## Task 6: 新增任务记忆查询接口

**Description:**  
提供任务记忆查询 API，支持查看当前活跃任务、查看当前 session 的任务列表、查看单个任务详情，便于前端展示和后端调试。

**Acceptance criteria:**
- [ ] 新增活跃任务查询接口
- [ ] 新增任务列表接口
- [ ] 新增任务详情接口

**Verification:**
- [ ] 测试通过：`python -m pytest backend/app/tests/test_task_memory_api.py -q`
- [ ] 手工检查：接口返回字段覆盖 `task_type`、`task_status`、`task_stage`、`last_error`

**Dependencies:** Task 2

**Files likely touched:**
- `backend/app/api/routers.py`
- `backend/app/schemas/request.py`
- `backend/app/tests/test_task_memory_api.py`

**Estimated scope:** Small

## Task 7: 在记忆管理页展示任务状态

**Description:**  
扩展现有前端“记忆管理”页，增加任务状态列表展示区，让这套任务连续性记忆可被直观看到和演示。

**Acceptance criteria:**
- [ ] 记忆管理页新增任务状态区域
- [ ] 能查看任务类型、任务状态、当前阶段、最近错误、最近活跃时间
- [ ] 页面在用户 ID 切换后能同步刷新任务状态

**Verification:**
- [ ] 构建通过：`cd front/agent_web_ui && npm run build`
- [ ] 手工检查：访问 `/memory` 可看到任务状态展示区

**Dependencies:** Task 6

**Files likely touched:**
- `front/agent_web_ui/src/api/memory.js`
- `front/agent_web_ui/src/views/MemoryPage.vue`

**Estimated scope:** Small

### Phase 4: Integration Polish

## Task 8: 让长期记忆、用户偏好与任务状态记忆协同工作

**Description:**  
在任务恢复时，确保系统既能拿到任务状态，也能保留长期记忆和用户偏好，形成“任务主导恢复、长期记忆补充背景、偏好约束回答风格”的组合上下文。

**Acceptance criteria:**
- [ ] 任务恢复上下文与长期记忆注入顺序明确
- [ ] 偏好和长期记忆不会覆盖任务状态的优先级
- [ ] 完成任务后可继续沉淀长期事实和偏好

**Verification:**
- [ ] 测试通过：`python -m pytest backend/app/tests/test_task_memory_context_integration.py -q`
- [ ] 手工检查：恢复任务时 history 中同时存在任务状态和长期记忆消息

**Dependencies:** Task 3, Task 6

**Files likely touched:**
- `backend/app/services/agent_service.py`
- `backend/app/services/memory_service.py`
- `backend/app/tests/test_task_memory_context_integration.py`

**Estimated scope:** Medium

## Task 9: 补充端到端记忆场景回归测试

**Description:**  
补齐围绕审批、失败、重试、恢复的端到端测试，确保这套记忆能力达到“可在简历中描述”的稳定程度。

**Acceptance criteria:**
- [ ] 覆盖“审批恢复继续执行”场景
- [ ] 覆盖“工具失败后继续恢复”场景
- [ ] 覆盖“自动重试后不丢上下文”场景

**Verification:**
- [ ] 测试通过：`python -m pytest backend/app/tests/test_task_memory_end_to_end.py -q`
- [ ] 汇总测试通过：`python -m pytest backend/app/tests/test_task_memory_*.py -q`

**Dependencies:** Task 4, Task 5, Task 8

**Files likely touched:**
- `backend/app/tests/test_task_memory_end_to_end.py`
- `backend/app/tests/test_task_memory_approval_flow.py`
- `backend/app/tests/test_task_memory_retry_flow.py`

**Estimated scope:** Medium

## Checkpoint: Complete
- [ ] `python -m pytest backend/app/tests/test_task_memory_*.py backend/app/tests/test_memory_service.py backend/app/tests/test_agent_service_memory_integration.py -q` 全部通过
- [ ] `cd front/agent_web_ui && npm run build` 通过
- [ ] 任务恢复主场景可手工验证
- [ ] 现有长期记忆、用户偏好和会话历史功能无回归

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| 任务恢复误命中新任务 | High | 明确继续类输入规则，默认只在同一 `session_id` 内恢复 |
| 状态更新散落在多条链路里导致不一致 | High | 所有状态转移都统一经过 `task_memory_service` |
| 审批恢复与任务恢复逻辑互相冲突 | High | 先保证 `waiting_approval` 的恢复优先级最高 |
| 前端只展示长期记忆和偏好，任务状态不可见 | Medium | 在现有记忆管理页增加任务状态区，先满足演示与调试 |
| 现有测试覆盖不足 | Medium | 新增独立 `test_task_memory_*` 套件，围绕核心场景设计 |

## Open Questions
- 当前实现先限定在同一 `session_id` 内恢复任务，是否后续再扩到跨 session
- 是否需要在后端 API 中提供“手动关闭活跃任务”的能力
- 技术专家链路是否和服务站链路共用一套 `task_stage` 命名规范，还是各自维护阶段枚举
