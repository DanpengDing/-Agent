# 售后多智能体系统 (Multi-Agent)

基于 FastAPI + OpenAI Agents SDK 构建的多智能体系统，提供智能问答、意图识别、任务分发等能力。

## 功能特性

- **意图理解与任务分发** — 主调度智能体解析用户意图，智能路由到对应专业智能体
- **技术专家咨询** — 技术专家智能体提供专业代码和技术问题解答
- **服务站查询** — 服务站智能体支持地理位置查询、服务站检索等功能
- **知识库检索** — 本地 Chroma 向量知识库，快速检索维修知识
- **流式响应** — 支持 SSE 流式输出，实时返回处理进度
- **Human-in-the-Loop** — 敏感操作人工审批机制
- **MCP 工具集成** — 支持搜索、百度地图等多种外部工具

## 项目结构

```
its_multi_agent/
├── backend/
│   ├── app/                    # 后端主服务
│   │   ├── api/               # FastAPI 路由、应用入口
│   │   ├── config/            # 环境变量与配置管理
│   │   ├── infrastructure/    # AI 客户端、数据库、日志、MCP 工具
│   │   ├── multi_agent/       # 智能体定义（调度、技术、服务站）
│   │   ├── prompts/           # 智能体提示词模板
│   │   ├── services/          # 业务逻辑层
│   │   ├── schemas/           # Pydantic 数据模型
│   │   ├── repositories/      # 数据访问层
│   │   └── tests/             # 单元测试
│   └── knowledge/             # 知识库服务（Chroma 向量存储）
├── front/
│   ├── agent_web_ui/          # 主前端 — 多智能体对话界面 (Vue 3 + Element Plus)
│   └── knowlege_platform_ui/  # 知识平台前端 (Vue 3 + Element Plus)
├── docs/                      # 文档
├── docker-compose.yml         # Docker 编排
└── .env.docker                # Docker 环境变量示例
```

## 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.8+ |
| Node.js | 16+（仅前端需要） |
| MySQL | 5.7+（可选，用于会话持久化） |
| Docker | 可选用于容器化部署 |

## 快速开始（本地开发）

### 前置要求

| 组件 | 用途 | 必选 |
|------|------|------|
| `backend/app` | 后端 API 服务（FastAPI） | **必选** |
| `front/agent_web_ui` | 主前端 — 多智能体对话界面 | **必选** |
| `front/knowlege_platform_ui` | 知识平台前端 | 可选 |
| `backend/knowledge` | 知识库服务（Chroma） | 可选 |

### 1. 克隆并进入项目

```bash
git clone <repo-url>
cd its_multi_agent
```

### 2. 启动后端（必选）

> 端口：**8000** | API 文档：http://127.0.0.1:8000/docs

```bash
# 进入后端目录
cd backend/app

# ① 安装 Python 依赖
pip install -r requirements.txt

# ② 创建 .env 配置文件
# 至少配置硅基流动 或 阿里百炼 之一，否则启动报错
cp .env.example .env 2>/dev/null || touch .env
```

`.env` 最小配置（二选一）：

```bash
# 方案一：硅基流动（推荐）
SF_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
SF_BASE_URL=https://api.siliconflow.cn/v1

# 方案二：阿里百炼
# AL_BAILIAN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
# AL_BAILIAN_BASE_URL=https://dashscope.aliyuncs.com
```

```bash
# ③ 启动后端
python api/main.py
```

### 3. 启动主前端（必选）

> 端口：**5173** | 地址：http://localhost:5173

另开一个终端：

```bash
# 回到项目根目录，进入主前端
cd its_multi_agent/front/agent_web_ui

# ① 安装依赖（仅首次）
npm install

# ② 启动开发服务器
npm run dev
```

前端直连 `http://127.0.0.1:8000`，无需额外配置。

测试账号：`root1` / `root2` / `root3`，密码均为 `123456`。

### 4. 启动知识平台前端（可选）

> 端口：**3000** | 地址：http://localhost:3000

```bash
cd its_multi_agent/front/knowlege_platform_ui

# ① 安装依赖（仅首次）
npm install

# ② 启动开发服务器
npm run dev
```

该前端通过 Vite proxy 将 `/api` 代理到 `http://127.0.0.1:8001`。

### 5. 启动知识库服务（可选）

> 端口：**9000**（Chroma MCP SSE）

```bash
cd its_multi_agent/backend/knowledge

# ① 安装依赖
pip install -r requirements.txt

# ② 启动知识库
python cli/main.py
```

## Docker 部署

适合不想手动配环境的场景，一键启动全部服务。

```bash
cd its_multi_agent

# 1. 配置环境变量
cp .env.docker .env
# 编辑 .env 填入你的 API Key

# 2. 启动所有服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止
docker-compose down
```

启动后访问：
- 前端：<http://localhost>
- 后端 API：<http://localhost:8000/docs>

## 运行测试

```bash
cd its_multi_agent/backend/app
python -m pytest tests/
```

## 配置说明

配置通过 `backend/app/.env` 文件管理，由 `config/settings.py` 统一加载。

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `SF_API_KEY` | 是* | 硅基流动 API Key |
| `SF_BASE_URL` | 是* | 硅基流动 Base URL |
| `AL_BAILIAN_API_KEY` | 是* | 阿里百炼 API Key |
| `AL_BAILIAN_BASE_URL` | 是* | 阿里百炼 Base URL |
| `MAIN_MODEL_NAME` | 否 | 主模型名称，默认 `Qwen/Qwen3-32B` |
| `SUB_MODEL_NAME` | 否 | 子模型名称 |
| `MYSQL_HOST` | 否 | MySQL 主机，默认 `localhost` |
| `MYSQL_PORT` | 否 | MySQL 端口，默认 `3306` |
| `MYSQL_USER` | 否 | MySQL 用户名，默认 `root` |
| `MYSQL_PASSWORD` | 否 | MySQL 密码 |
| `MYSQL_DATABASE` | 否 | MySQL 数据库名，默认 `multi_agent_db` |
| `KNOWLEDGE_MCP_URL` | 否 | 知识库 MCP SSE 地址，默认 `http://127.0.0.1:9000/sse` |
| `BAIDUMAP_AK` | 否 | 百度地图 AK（服务站查询需要） |

\* 至少配置硅基流动或阿里百炼之一，否则后端启动会报错。

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         API 层 (FastAPI + Uvicorn)               │
├─────────────────────────────────────────────────────────────────┤
│                        服务层                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────────┐  │
│  │ AgentService │ │ HITLService  │ │ SessionService          │  │
│  └──────────────┘ └──────────────┘ └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                        智能体层                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐     │
│  │ Orchestrator │ │  Technical   │ │  Service Station     │     │
│  │   Agent      │ │   Agent      │ │  Agent               │     │
│  └──────────────┘ └──────────────┘ └──────────────────────┘     │
├─────────────────────────────────────────────────────────────────┤
│                       基础设施层                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐     │
│  │ OpenAI SDK   │ │ MCP Servers  │ │ MySQL + Chroma       │     │
│  └──────────────┘ └──────────────┘ └──────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## License

MIT License
