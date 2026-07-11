# AI 数字人景区导览系统

## 数字人首版

管理端的“数字人形象管理”支持按“人物身份 + VRM 外观/服装版本”维护讲解员，控制每个景区可见版本、唯一默认人物和排序。游客端只会看到当前景区生效的版本，并会在浏览器本地记住个人选择。

VRM 文件保存在本地 `backend/uploads/avatars/`，上传限制为 80MB，服务端检查 `.vrm` 与 GLB 文件头。执行 `alembic upgrade head` 后，可用 `backend/scripts/seed_avatars.py` 将十个自制灵山讲解员导入指定景区；TTS 播放会驱动 VRM 的待机、思考、聆听、眨眼和音量嘴型。WebGL 或模型加载失败时仍可使用文本与音频讲解。

项目默认使用 `pgvector` 检索。向量在 PostgreSQL 中固定保存为 `DOUBLE PRECISION[]`（SQLite 测试环境保存为 JSON），因此切换 `RAG_VECTOR_BACKEND` 不会改变表结构。若本机 PostgreSQL 未安装该扩展，可仅在本地 `backend/.env` 或 `backend/.env.docker` 设置 `RAG_VECTOR_BACKEND=json`；该模式在应用侧计算余弦距离，并受 `RAG_JSON_CANDIDATE_LIMIT`（默认 2000 条）保护，适合比赛演示和中小型资料库。

这是一个面向比赛作品的前后端单仓库骨架。第一阶段目标是打通游客/管理员登录、JWT 鉴权、角色路由守卫、PostgreSQL 用户表和登录日志，为后续数字人、RAG 知识库、语音交互和管理后台开发打地基。

## 技术栈

- 前端：Vue 3 + Vite + TypeScript + Vue Router + Pinia + Element Plus
- 后端：FastAPI + SQLAlchemy + Alembic + PostgreSQL + JWT + bcrypt
- 数据库：PostgreSQL，本地数据库名 `ai_tour_guide`
- 游客导览：文字/语音提问、RAG 回答来源与百炼语音播报。

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

2. 启动本地 pgvector PostgreSQL：

   ```powershell
   .\scripts\start-pgvector.ps1
   ```

   脚本会复用 `backend/.env` 中的数据库账号、密码、库名和首选端口；如果首选端口已被占用，会自动在 `5433-5450` 中选择空闲端口，并生成被 Git 忽略的 `backend/.env.docker` 供后端和 Alembic 使用。数据库数据保存在项目的 `.local-data/pgvector-postgres/`，不会提交 Git。

   如果协作者不使用 Docker，也可以创建本机数据库后执行 SQL 初始化表结构和默认管理员：

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

初始化脚本只会在管理员不存在时创建该账号；重复执行不会重置已有管理员的密码。

## pgvector

本项目的 Docker 数据库镜像已经内置 pgvector。安装扩展后执行 `CREATE EXTENSION IF NOT EXISTS vector`，并保持 `RAG_VECTOR_BACKEND=pgvector`，检索将改由数据库计算余弦距离；未安装扩展时使用 `RAG_VECTOR_BACKEND=json`。两种模式共用同一份向量数据，无需重新建表或重建索引。不要将 PostgreSQL 数据目录、真实密码或 API Key 提交到 Git。

## 认证测试

```powershell
cd backend
pip install -r requirements-dev.txt
pytest
```

认证测试使用内存 SQLite，不会写入本地 PostgreSQL。

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
