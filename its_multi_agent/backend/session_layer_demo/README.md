# MySQL + Redis 会话分层方案示例

这个目录是一个独立示例，不依赖现有 `app/` 目录，也不会修改项目里的其他模块。

## 目标

把当前“本地文件保存会话”的思路，替换成企业里更常见的：

- Redis：保存热点会话上下文，支撑高频读取
- MySQL：保存持久化消息、会话元数据、审计数据
- SessionService：统一封装“先查 Redis，miss 再回源 MySQL，结束后回写”的链路

## 主链路

1. 前端请求 `POST /api/query`
2. API 层调用 `SessionService.build_runtime_context()`
3. `SessionService` 先查 Redis
4. Redis miss 时回源 MySQL，再把最近上下文回填 Redis
5. 将本轮用户消息拼入上下文，交给 orchestrator / agent
6. Agent 执行过程中持续返回 SSE
7. 流结束后调用 `SessionService.persist_round()`
8. 先更新 Redis 热数据，再异步落 MySQL

## 目录结构

- `models.py`
  会话和消息的数据模型
- `repositories.py`
  Redis / MySQL 仓储接口及内存版示例实现
- `session_service.py`
  会话主链路实现
- `api_example.py`
  一个简化版 SSE 接口骨架
- `schema.sql`
  MySQL 表结构示例

## 为什么这样分层

- Redis 解决“每轮都要快速取最近上下文”
- MySQL 解决“持久化、审计、统计分析”
- Service 层隔离缓存逻辑和持久化逻辑，避免 API 层直接拼 Redis/MySQL 细节

## 一致性策略

这里采用的是“请求主链路优先保证响应速度，持久化最终一致”：

1. 先返回 SSE，不阻塞首包
2. 结束后先更新 Redis
3. 再异步写 MySQL
4. 如果 MySQL 失败，可由重试任务继续补偿

如果业务对强一致要求更高，也可以把 `persist_round()` 改成同步写 MySQL 成功后再发 finish。
