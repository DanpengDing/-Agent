# 售后多智能体问答系统 - 面试问答

> 项目路径：`D:\BaiduNetdiskDownload\bj250716\its_multi_agent`
> 技术栈：Python/FastAPI + OpenAI Agents SDK + MySQL + Chroma向量库 + MCP协议

## 目录

- [一、项目深度理解](#一项目深度理解)
- [二、技术原理](#二技术原理)
- [三、代码设计](#三代码设计)
- [四、性能与扩展](#四性能与扩展)
- [五、安全与生产](#五安全与生产)

---

## 一、项目深度理解

### 1. 为什么要用多智能体而不是单一大模型？

**标准答案要点：**

- **职责分离**：不同Agent专注不同领域（Orchestrator做调度、Technical做技术咨询、Service做服务站查询），避免单一模型负载过重
- **可维护性**：各Agent独立开发、测试、迭代，不会相互影响
- **工具解耦**：Orchestrator通过`function_tool`调用子Agent，子Agent各自绑定不同工具（MCP工具、本地知识库），职责清晰
- **流式架构**：主Agent用`Runner.run_streamed`流式输出，子Agent用`Runner.run`同步执行，分工明确
- **并行能力**：多个子Agent可以并行初始化（如`search_mcp_client`、`knowledge_mcp_client`并发连接）

**面试官考察意图：**
考察候选人对多Agent架构设计理念的理解，是否理解"专业化分工"和"组合优于单体"的设计原则。

**加分回答：**
- 提到OpenAI Agents SDK的`Agent`对象与`Runner`分离机制
- 提到MCP协议的工具发现和调用机制如何支撑多Agent协作
- 提到Human-in-the-Loop审批与Agent职责的关联（Orchestrator发现问题才触发审批）

---

### 2. Orchestrator Agent是如何做意图识别的？

**标准答案要点：**

- **提示词驱动**：通过`load_prompt("orchestrator_v1")`加载专门的提示词模板，定义了任务识别规则和工具选择原则
- **工具路由**：
  - 技术/资讯类问题 → `consult_technical_expert`
  - 服务站/导航类问题 → `query_service_station_and_navigate`
- **多任务处理**：按顺序依次调用多个工具（等待上一个返回后再调用下一个）
- **停止条件**：用户明确要求的所有任务都调用对应工具后立即停止，不重复调用

**代码证据：**
```python
# orchestrator_agent.py
orchestrator_agent = Agent(
    name="主调度智能体",
    instructions=load_prompt("orchestrator_v1"),
    model=sub_model,  # 通用模型，干活为主
    model_settings=ModelSettings(temperature=0),
    tools=AGENT_TOOLS,  # [consult_technical_expert, query_service_station_and_navigate]
)
```

```python
# orchestrator.md 提示词核心原则
### 1. 任务完整性原则
- 只识别用户明确请求的任务
- 不要推测或添加用户没有明确提到的任务
```

**面试官考察意图：**
考察候选人对意图识别实现的理解——不是靠硬编码规则，而是通过提示词+工具定义来实现灵活路由。

**加分回答：**
- 提到Query Rewrite服务如何优化用户输入再传给Orchestrator
- 提到`context=user_query`参数如何辅助Agent理解当前任务
- 提到`max_turns=5`限制防止无限循环

---

### 3. Human-in-the-Loop在什么场景触发？

**标准答案要点：**

- **触发场景**：`query_service_station_and_navigate`工具（服务站查询/导航）需要人工审批
- **实现机制**：
  - 工具使用`@function_tool(needs_approval=True)`装饰器
  - 模型决定调用该工具时，SDK会暂停run，将待审批项放入`interruptions`
  - 同时生成可恢复的`state`（通过`result.to_state()`）
  - 系统创建`PendingApproval`记录，返回token给前端
- **审批流程**：前端展示审批UI → 用户确认/拒绝 → 后端调用`resolve_pending_approval` → 恢复run或终止

**代码证据：**
```python
# technical_agent.py
@function_tool(needs_approval=True)
async def query_service_station_and_navigate(query: str) -> str:
    # needs_approval=True 使SDK暂停run，等待人工审批
```

```python
# agent_service.py - 检测审批中断
interruptions = cls._extract_interruptions(streaming_result)
if interruptions:
    pending = hitl_service.create_pending_approval(
        user_id=user_id, session_id=session_id, query=user_query,
        state=state, interruptions=interruptions, ...
    )
    yield "data: " + ResponseFactory.build_human_approval(token=pending.token, ...)
```

**面试官考察意图：**
考察候选人对"Human-in-the-Loop"模式的理解，特别是如何在AI自动化和人工控制之间取得平衡。

**加分回答：**
- 提到当前实现用内存存储`PendingApproval`（`hitl_service._pending`），多实例部署需改用Redis/DB
- 提到OpenTelemetry追踪链路如何记录审批流程

---

## 二、技术原理

### 1. MCP协议的工作机制？如何扩展新工具？

**标准答案要点：**

- **MCP Server类型**：使用`MCPServerSse`（SSE模式），通过HTTP+SSE建立持久连接
- **配置方式**：在`mcp_servers.py`中定义每个MCP客户端
- **工具发现**：通过`await mcp_instance.list_tools()`获取工具列表
- **工具调用**：通过`await mcp_instance.call_tool(tool_name, tool_args)`执行
- **扩展方式**：新增MCP Server配置 + 在Agent的`mcp_servers`列表中注册

**代码证据：**
```python
# mcp_servers.py
search_mcp_client = MCPServerSse(
    name="通用联网搜索",
    params={
        "url": f"{settings.DASHSCOPE_BASE_URL}",
        "headers": {"Authorization": f"Bearer {settings.AL_BAILIAN_API_KEY}"},
        "timeout": 60,
        "sse_read_timeout": 60 * 30,
    },
    client_session_timeout_seconds=60 * 10,
    cache_tools_list=True,
)

# technical_agent.py - 绑定MCP服务器
technical_agent = Agent(
    ...
    tools=[query_knowledge],
    mcp_servers=[search_mcp_client, knowledge_mcp_client],
)
```

**面试官考察意图：**
考察候选人对MCP（Model Context Protocol）协议的理解，以及如何在实际项目中集成外部工具。

**加分回答：**
- 提到`cache_tools_list=True`避免每次调用都去获取工具列表
- 提到工具的输入输出schema定义（`tool.inputSchema`）
- 提到`AsyncExitStack`管理多个MCP连接的 lifecycle

---

### 2. Chroma向量库如何实现语义检索？相似度阈值是多少？

**标准答案要点：**

- **项目中的实现**：知识库通过独立的`knowledge`服务暴露，不是直接在backend使用Chroma
- **检索方式**：通过`query_knowledge`工具调用`KNOWLEDGE_BASE_URL`服务
- **参数**：`top_k`参数控制返回结果数量
- **向量匹配**：Chroma使用余弦相似度进行向量匹配

**代码证据：**
```python
# knowledge_base.py
@function_tool
async def query_knowledge(question: str) -> Dict:
    response = await client.post(
        url=f"{settings.KNOWLEDGE_BASE_URL}/query",
        json={"question": question},
        timeout=60
    )
    return response.json()

# mcp_servers.py - 知识库MCP
knowledge_mcp_client = MCPServerSse(
    name="知识库问答",
    params={"url": f"{settings.KNOWLEDGE_MCP_URL}", ...},
    cache_tools_list=True,
)
```

**面试官考察意图：**
考察候选人对向量数据库的语义检索原理的理解，以及如何在多Agent系统中集成知识库。

**加分回答：**
- 提到Chroma的embedding模型选择对检索效果的影响
- 提到可结合关键词过滤（如BM25）优化纯向量检索的精确度
- 提到知识库如何做增量更新而非全量重建

---

### 3. SSE流式响应是如何实现的？

**标准答案要点：**

- **技术选型**：使用Server-Sent Events（SSE），通过`async for`遍历`streaming_result.stream_events()`
- **事件类型处理**：
  - `raw_response_event` → 文本增量（`ResponseTextDeltaEvent`）
  - `run_item_stream_event` → 工具调用/输出（`tool_called`、`tool_output`）
  - `agent_updated_stream_event` → Agent切换通知
- **响应格式**：`data: {...}\n\n`（JSON序列化后加双换行）
- **前端处理**：EventSource接受SSE，逐条解析JSON

**代码证据：**
```python
# agent_service.py
streaming_result = Runner.run_streamed(
    starting_agent=orchestrator_agent,
    input=chat_history,
    context=user_query,
    max_turns=5,
)
async for chunk in process_stream_response(streaming_result):
    yield chunk

# stream_response_service.py
async def process_stream_response(streaming_result):
    async for event in streaming_result.stream_events():
        if event.type == "raw_response_event":
            if isinstance(event.data, ResponseTextDeltaEvent):
                yield "data: " + ResponseFactory.build_text(
                    delta_text, ContentKind.ANSWER
                ).model_dump_json() + "\n\n"
```

**面试官考察意图：**
考察候选人对流式响应技术的掌握，包括SSE协议、后端异步生成、前端逐行处理。

**加分回答：**
- 提到思考链（Reasoning）事件单独处理：`ResponseReasoningTextDeltaEvent`
- 提到`RunConfig(tracing_disabled=True)`避免追踪数据干扰流式输出
- 提到如何通过`ContentKind`枚举区分不同内容类型（ANSWER、PROCESS、THINKING）

---

## 三、代码设计

### 1. 系统的异常处理是如何设计的？

**标准答案要点：**

- **分层捕获**：
  - 工具层：各工具函数内部try-catch，返回错误信息（如`query_knowledge`返回`{"status": "error"}`）
  - 服务层：`agent_service.py`统一捕获整条链路异常，记录traceback，发送失败消息
  - Agent层：子Agent异常向上抛出，由`consult_technical_expert`等桥接函数捕获
- **重试机制**：`process_task`支持一次自动重试，flag参数控制
- **日志追踪**：异常信息同时写入`error.log`和OpenTelemetry span

**代码证据：**
```python
# agent_service.py 异常处理
except Exception as exc:
    logger.error("[AgentService] failed user=%s session=%s query=%s error=%s",
                 user_id, session_id, original_query, exc)
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, str(exc)))

    text = f"系统处理请求时出现异常：{exc}"
    yield "data: " + ResponseFactory.build_text(text, ContentKind.PROCESS).model_dump_json() + "\n\n"

    if flag:
        # 重试一次
        async for item in MultiAgentService.process_task(request, flag=False):
            yield item
```

```python
# knowledge_base.py 工具层异常处理
except httpx.HTTPError as e:
    logger.error(f"发送请求获取知识库服务下的知识库数据失败:{str(e)}")
    return {"status": "error", "error_msg": f"发送请求获取知识库服务下的知识库数据失败:{e}"}
```

**面试官考察意图：**
考察候选人对异常处理的设计模式理解，特别是在异步、流式、多Agent协作场景下的异常管理。

**加分回答：**
- 提到日志分级（app.log写INFO，error.log写ERROR，agent_debug.log写DEBUG）
- 提到`traceback.format_exc()`如何帮助定位异常发生位置
- 提到连接池异常不会直接抛出，而是等待重试或降级

---

### 2. 如何保证多Agent调用的确定性？

**标准答案要点：**

- **模型温度**：所有Agent使用`temperature=0`，保证相同输入产生相同输出
- **提示词约束**：Orchestrator提示词明确禁止重复调用、禁止推测需求、禁止添加历史任务
- **工具选择唯一性**：每类任务对应唯一工具，维修站查询必须用`query_service_station_and_navigate`
- **最大轮次限制**：`max_turns=5`防止无限循环

**代码证据：**
```python
# orchestrator_agent.py
model=sub_model,
model_settings=ModelSettings(temperature=0),

# orchestrator.md 停止条件
**何时停止调用工具**：
- 用户明确要求的所有任务都已调用对应工具
- 不要重复调用同一个工具处理同一个查询
- 不要"以防万一"再调用一次工具
- 同一查询最多调用3次！
```

**面试官考察意图：**
考察候选人对AI系统不确定性问题（hallucination、重复调用）的理解，以及如何通过工程约束保证系统行为可预测。

**加分回答：**
- 提到Structured Output Service如何归一化最终输出格式
- 提到Query Rewrite如何标准化用户输入，减少歧义
- 提到`tracing_disabled=True`避免调试信息干扰确定性

---

### 3. 数据库连接池是如何管理的？

**标准答案要点：**

- **单例模式**：`DatabasePool`类使用类变量`_pool`存储全局唯一实例
- **懒加载**：首次调用`get_pool()`时才初始化
- **连接池库**：使用`DBUtils.PooledDB`，基于pymysql
- **配置项**：通过`settings`对象注入（host、port、user、password、database、max_connections等）
- **获取连接**：通过`.connection()`方法从池中借用，用完自动归还

**代码证据：**
```python
# database_pool.py
class DatabasePool:
    _pool = None  # 类变量，存储全局唯一连接池

    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            cls._pool = PooledDB(
                creator=pymysql,
                maxconnections=settings.MYSQL_MAX_CONNECTIONS,
                host=settings.MYSQL_HOST,
                port=settings.MYSQL_PORT,
                database=settings.MYSQL_DATABASE,
                charset=settings.MYSQL_CHARSET,
                connect_timeout=settings.MYSQL_CONNECT_TIMEOUT,
            )
        return cls._pool

    @classmethod
    def get_connection(cls):
        return cls.get_pool().connection()

pool = DatabasePool.get_pool()  # 模块加载时初始化
```

**面试官考察意图：**
考察候选人对数据库连接池原理的理解，以及如何在Python项目中正确管理连接资源。

**加分回答：**
- 提到PooledDB的`mincached`、`maxcached`、`maxshared`等参数含义
- 提到`blocking=True`时连接池满会阻塞等待
- 提到当前实现适合单实例部署，多实例需考虑连接池统一管理

---

## 四、性能与扩展

### 1. 如果知识库增长到100万条，如何优化检索？

**标准答案要点：**

- **分区/分片**：按业务领域（硬件、软件、网络）分区建库，检索时先路由到对应分区
- **层次索引**：结合倒排索引（关键词）+ 向量索引（语义），先用BM25过滤再用向量匹配
- **缓存策略**：热点知识缓存到Redis，减少重复查询
- **量化压缩**：向量维度压缩（如从float32到int8），降低存储和计算开销
- **批量检索**：多个问题合并成一个batch，利用GPU并行加速

**面试官考察意图：**
考察候选人对大规模向量检索问题的理解，以及如何在成本和效果之间取得平衡。

**加分回答：**
- 提到HNSW替代IVF-PQ索引，提升检索速度
- 提到知识库增量更新而非全量重建
- 提到A/B测试验证优化效果

---

### 2. 如何添加新的Agent类型？

**标准答案要点：**

- **步骤1**：在`prompts/`目录下创建新的提示词文件（如`new_agent.md`）
- **步骤2**：创建Agent实例，绑定model和tools
- **步骤3**：在`agent_factory.py`中添加对应的function_tool作为桥接
- **步骤4**：在Orchestrator的提示词中添加新工具的调用规则
- **步骤5**：测试验证

**代码证据：**
```python
# 添加新Agent示例（technical_agent.py）
new_agent = Agent(
    name="新产品专家",
    instructions=load_prompt("new_agent"),
    model=sub_model,
    model_settings=ModelSettings(temperature=0),
    tools=[...],
    mcp_servers=[...],
)

# 添加桥接工具（agent_factory.py）
@function_tool
async def consult_new_expert(query: str) -> str:
    result = await Runner.run(new_agent, input=query, ...)
    return result.final_output

# 更新AGENT_TOOLS列表
AGENT_TOOLS = [consult_technical_expert, query_service_station_and_navigate, consult_new_expert]
```

**面试官考察意图：**
考察候选人对Agent系统扩展性的理解，以及如何遵循现有架构模式添加新功能。

**加分回答：**
- 提到提示词模板的热更新（`load_prompt`支持动态加载）
- 提到MCP工具发现机制如何自动获取新工具列表
- 提到测试用例设计（单元测试覆盖新Agent逻辑）

---

### 3. 高并发场景下如何保证稳定性？

**标准答案要点：**

- **连接池管理**：数据库连接池限制最大连接数，超出等待而非无限创建
- **超时控制**：所有I/O操作设置timeout（HTTP请求60s、MCP读取30min）
- **流式处理**：SSE响应立即返回，避免长时间阻塞
- **资源隔离**：各Agent独立运行，不会因某一个慢查询拖垮其他请求
- **重试限制**：最多重试1次，防止级联失败
- **日志监控**：分级日志+OpenTelemetry追踪，快速定位瓶颈

**代码证据：**
```python
# MCP超时配置
sse_read_timeout=60 * 30,  # 30分钟SSE读取超时

# HTTP客户端超时
response = await client.post(url, json={"question": question}, timeout=60)

# 数据库连接超时
connect_timeout=settings.MYSQL_CONNECT_TIMEOUT

# Agent重试限制
if flag:
    async for item in MultiAgentService.process_task(request, flag=False):
        yield item
# 第二次flag=False，不会再次重试
```

**面试官考察意图：**
考察候选人对高并发系统稳定性设计的理解，特别是在IO密集型（网络、数据库）的异步场景下如何做保护。

**加分回答：**
- 提到限流（Rate Limiting）策略
- 提到熔断器模式避免雪崩
- 提到Docker Compose水平扩展多实例

---

## 五、安全与生产

### 1. 如何防止用户输入注入攻击？

**标准答案要点：**

- **Guardrail输入过滤**：API入口集成DFA敏感词过滤器
  - 通用敏感词命中 → 直接拒绝请求
  - 业务敏感词命中 → 替换为`***`后继续处理
- **DFA算法**：构建以敏感词为key的状态转移图，实现O(1)复杂度的字符串匹配
- **参数化传递**：Agent输入通过`Runner.run`传递，不做字符串拼接
- **提示词隔离**：用户输入作为`input`而非直接拼入系统提示词

**代码证据：**
```python
# guardrail_service.py
class DFAFilter:
    def filter_text(self, text: str, replace_char: str = "*") -> tuple[str, list[str]]:
        # DFA状态机匹配敏感词
        ...

class GuardrailService:
    def check_input(self, text: str) -> GuardrailCheckResult:
        # 第1步：检查通用敏感词（拒绝）
        # 第2步：检查业务敏感词（替换）
        ...

# API入口集成（在routers中）
result = guardrail_service.check_input(user_input)
if result.blocked:
    return {"status": "blocked", "reason": "敏感词"}
```

**面试官考察意图：**
考察候选人对LLM应用安全风险（Prompt Injection、敏感信息泄露）的理解，以及如何用工程手段防御。

**加分回答：**
- 提到热更新敏感词库（`check_and_reload()`）
- 提到敏感词库结构（`common`vs`business`分级）
- 提到输出过滤（最终输出也需检查敏感词）

---

### 2. 日志中如何保护用户隐私？

**标准答案要点：**

- **日志脱敏**：用户查询`query`在日志中截断（`[:200]`）避免完整内容暴露
- **分级日志**：
  - `app.log`记录业务操作（INFO级）
  - `error.log`记录错误（ERROR级）
  - `agent_debug.log`记录详细调试信息（DEBUG级，仅保留7天）
- **日志格式**：不含PII（个人身份信息），只记录user_id/session_id用于关联
- **文件权限**：日志目录`logs/`权限控制，仅应用用户可读

**代码证据：**
```python
# 日志记录时的隐私保护
logger.info("[AgentService] start user=%s session=%s query=%s",
            user_id, session_id, original_query)  # query可能截断

# agent_service.py 中的工具参数截断
logger.info("[Stream] tool_called name=%s args=%s", tool_name, str(tool_args)[:500])

# knowledge_base.py
logger.error(f"发送请求获取知识库服务下的知识库数据失败:{str(e)}")
```

**面试官考察意图：**
考察候选人对日志安全的理解，特别是在 GDPR 等隐私法规背景下的日志管理实践。

**加分回答：**
- 提到日志轮转（`TimedRotatingFileHandler`，保留30/60/7天）
- 提到集中式日志收集时的脱敏方案（如ELK中做数据脱敏）
- 提到OpenTelemetry的采样策略（高流量时降采样）

---

### 3. Docker化部署的关键配置？

**标准答案要点：**

- **多阶段构建**：Python应用使用`python:3.10-slim`减少镜像体积
- **环境变量**：API Key等敏感配置通过`.env`文件注入，不写在Dockerfile
- **健康检查**：`HEALTHCHECK`检测`/health`端点
- **资源限制**：`--memory`限制内存，`--cpus`限制CPU
- **非root用户**：`USER`切换到非root用户运行
- **日志收集**：stdout输出到`docker logs`，便于`docker logs`查看

**Dockerfile关键配置：**
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "api.main:create_fast_api", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose关键配置：**
```yaml
services:
  backend:
    build: .
    env_file: .env
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**面试官考察意图：**
考察候选人对Docker化部署的最佳实践理解，特别是在安全、性能、可观测性方面的配置。

**加分回答：**
- 提到`docker-compose`多服务编排（backend、knowledge service）
- 提到前端静态资源通过Nginx反代或CDN加速
- 提到OpenTelemetry导出器配置（OTLPendpoint）用于生产环境追踪

---

## 附录：关键代码路径索引

| 功能 | 文件路径 |
|------|----------|
| Orchestrator Agent | `backend/app/multi_agent/orchestrator_agent.py` |
| 意图识别提示词 | `backend/app/prompts/orchestrator.md` |
| Human-in-the-Loop | `backend/app/services/hitl_service.py` |
| MCP工具集成 | `backend/app/infrastructure/tools/mcp/mcp_servers.py` |
| SSE流式响应 | `backend/app/services/stream_response_service.py` |
| 数据库连接池 | `backend/app/infrastructure/database/database_pool.py` |
| 敏感词过滤 | `backend/app/services/guardrail_service.py` |
| 日志管理 | `backend/app/infrastructure/logging/logger.py` |
| Agent工厂 | `backend/app/multi_agent/agent_factory.py` |
| 主服务逻辑 | `backend/app/services/agent_service.py` |

---

*文档生成时间：2026/05/03*
*项目版本：基于 `its_multi_agent` 最新代码*