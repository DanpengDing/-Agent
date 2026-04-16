# 前端项目 (Front End)

本目录包含两个前端 Vue 3 项目。

## 项目结构

```
front/
├── agent_web_ui/         # 售后多智能体 Multi-Agent 管理界面
│   ├── src/              # 源代码
│   └── package.json      # 项目配置
└── knowlege_platform_ui/ # 知识平台界面
    ├── src/              # 源代码
    └── package.json      # 项目配置
```

## 快速启动

### agent_web_ui（售后多智能体）

```bash
cd its_multi_agent/front/agent_web_ui

# 安装依赖
npm install

# 开发模式启动（开发环境）
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

**配置说明：**
- 开发服务器端口：`3000`
- API 代理目标：`http://127.0.0.1:8001`（后端服务地址）
- 修改代理目标请编辑 `vite.config.js` 中的 `server.proxy`

### knowlege_platform_ui（知识平台）

```bash
cd its_multi_agent/front/knowlege_platform_ui

# 安装依赖
npm install

# 开发模式启动
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

**配置说明：**
- 默认端口：`5173`
- 无 API 代理配置（如需，请自行在 `vite.config.js` 中添加）

## 环境要求

- Node.js >= 16.x
- npm >= 8.x

## 生产部署

### 静态部署

构建后的文件在 `dist/` 目录，可部署到任意静态文件服务器（如 Nginx、Caddy、OSS 等）。

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # agent_web_ui
    location / {
        root /path/to/agent_web_ui/dist;
        try_files $uri $uri/ /index.html;
    }

    # 代理 API 请求到后端
    location /api/ {
        proxy_pass http://127.0.0.1:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 技术栈

- **框架**：Vue 3.4+
- **构建工具**：Vite 5.x
- **UI 组件库**：Element Plus 2.x
- **路由**：Vue Router 4.x
- **Markdown 渲染**：marked
