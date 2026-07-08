# AI 数字人景区导览系统

这是一个面向比赛作品的前后端单仓库骨架。第一阶段目标是打通游客/管理员登录、JWT 鉴权、角色路由守卫、PostgreSQL 用户表和登录日志，为后续数字人、RAG 知识库、语音交互和管理后台开发打地基。

## 技术栈

- 前端：Vue 3 + Vite + TypeScript + Vue Router + Pinia + Element Plus
- 后端：FastAPI + SQLAlchemy + Alembic + PostgreSQL + JWT + bcrypt
- 数据库：PostgreSQL，本地数据库名 `ai_tour_guide`

## 目录结构

```text
.
├── backend/      # FastAPI 后端
├── frontend/     # Vue3 前端
├── docs/         # 接口和开发文档
└── scripts/      # 本地开发脚本
```

## 快速启动

1. 复制本地环境变量文件：

   ```powershell
   Copy-Item backend\.env.example backend\.env
   Copy-Item frontend\.env.example frontend\.env
   ```

   然后按本机情况修改 `backend/.env`：

   - `DATABASE_URL`：PostgreSQL 用户名、密码、端口和数据库名
   - `SECRET_KEY`：本地 JWT 密钥，协作者各自生成一串长随机值即可
   - `DASHSCOPE_API_KEY`、`DASHSCOPE_API_HOST`、`LLM_BASE_URL`、`DASHSCOPE_BASE_URL`：阿里云百炼/通义千问配置

   `frontend/.env` 默认指向 `http://localhost:8000/api`，本地端口不变时无需修改。

2. 创建数据库：

   ```powershell
   .\scripts\create-database.ps1
   ```

   如果协作者不想跑 Alembic，也可以直接执行 SQL 初始化表结构和默认管理员：

   ```powershell
   psql -h localhost -p 5432 -U postgres -d ai_tour_guide -f backend/sql/init_auth_schema.sql
   ```

3. 安装并初始化后端：

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   alembic upgrade head
   python scripts\init_admin.py
   uvicorn app.main:app --reload
   ```

   如果本机策略不允许创建 `.venv`，可以改用项目内依赖目录：

   ```powershell
   cd backend
   python -m pip install -r requirements.txt --target .python-packages
   $env:PYTHONPATH=(Join-Path (Get-Location) ".python-packages")
   python -m alembic upgrade head
   python scripts\init_admin.py
   python -m uvicorn app.main:app --reload
   ```

4. 安装并启动前端：

   ```powershell
   cd frontend
   npm.cmd install
   npm.cmd run dev
   ```

5. 访问：

   - 前端：http://localhost:5173
   - 后端文档：http://localhost:8000/docs

默认管理员账号：`admin / 123456`。

## 环境变量

真实密钥和数据库密码只放在本地 `.env`，不要提交 Git。示例配置见：

- `backend/.env.example`
- `frontend/.env.example`

默认大模型供应商配置为阿里云百炼/通义千问：

```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_API_HOST=your-workspace.cn-beijing.maas.aliyuncs.com
LLM_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
DASHSCOPE_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com/api/v1
LLM_CHAT_MODEL=qwen-plus
LLM_EMBEDDING_MODEL=text-embedding-v4
```

本地开发时只修改 `backend/.env` 里的 `DASHSCOPE_API_KEY`，不要把真实 API Key 写入 `.env.example`。
