# 灵境智游：AI 数字人景区导览系统

面向景区游客与运营人员的一体化智能导览系统。游客无需注册或登录，在首页选择景区后即可获得 30 天内可恢复的匿名身份，使用景点浏览、个性化路线、数字人讲解和文字/语音问答；管理员通过独立入口维护景区内容、知识库、数字人、语音服务及运营数据。清除浏览器本地数据后，原匿名身份将无法恢复。

## 当前能力

- 游客免登录：景区选择、匿名会话恢复、景点浏览和路线推荐。
- 智能导览：RAG 检索、连续问答、来源展示、ASR 语音提问和流式 TTS 播放。
- 路线联动：按兴趣、时长和起点推荐路线，并把路线、当前景点、游览进度和兴趣上下文传入数字人讲解。
- 数字人管理：10 个自制 VRM，支持人物与服装版本、景区上架、默认人物、音色和讲解风格配置。
- 数字人表现：待机、欢迎、聆听、思考、指路、讲解、眨眼及音量嘴型；模型或 WebGL 不可用时降级为文字与语音。
- 运营闭环：景点、素材、路线、知识库管理，游客评价与感受度分析，数据大屏和日报/周报。

## 数字人首版

管理端的“数字人形象管理”支持按“人物身份 + VRM 外观/服装版本”维护讲解员，控制每个景区可见版本、唯一默认人物和排序。游客端只会看到当前景区生效的版本，并会在浏览器本地记住个人选择。

VRM 文件保存在本地 `backend/uploads/avatars/`，上传限制为 80MB，服务端检查 `.vrm` 与 GLB 文件头。执行 `alembic upgrade head` 后，可用 `backend/scripts/seed_avatars.py` 将十个自制灵山讲解员导入指定景区；游客端只下载当前选中的一个模型，模型接口支持私有长期缓存、ETag 和字节范围请求，Three.js/VRM 运行时在进入数字人舞台后才按需加载。TTS 播放会驱动 VRM 的待机、思考、聆听、眨眼和音量嘴型，并根据欢迎、路线与方向语义切换动作；语音支持后台在火山引擎实时 TTS 与千问 TTS 间配置默认、备用和人物专属音色，游客端按 24kHz PCM 分片边接收边播放。WebGL 或模型加载失败时仍可使用文本与音频讲解。

项目默认使用 Docker 中的 PostgreSQL + pgvector 检索。向量在 PostgreSQL 中固定保存为 `DOUBLE PRECISION[]`（SQLite 测试环境保存为 JSON），因此切换 `RAG_VECTOR_BACKEND` 不会改变表结构。仅在无法使用 pgvector 的临时环境中，可在本地 `backend/.env` 设置 `RAG_VECTOR_BACKEND=json`；该模式在应用侧计算余弦距离，并受 `RAG_JSON_CANDIDATE_LIMIT`（默认 2000 条）保护。

系统采用游客免登录模式：游客在公开首页选择景区后自动获得可恢复的匿名身份，并直接进入数字人导览；管理员通过独立入口登录。系统同时包含景点浏览、路线推荐、智能导览，以及景点、素材、路线、知识库、数字人和运营统计等管理功能。

## 游客感受度与数据大屏

每次数字导览问答完成后，系统会异步生成固定结构的主题、意图、情绪和服务问题标签，不阻塞游客获得回答。游客可在会话中自愿提交 1–5 分、体验标签和文字建议；管理端“游客感受度大屏”按景区与日期汇总服务游客数、回答成功率、响应时长、负向反馈率、热门问题和满意度趋势。

“游客洞察”工作台用于生成日报或周报，并对负向反馈、待关注事项和分析失败记录进行筛选、重试和解决闭环。报告模型只接收聚合统计快照，不接收游客账号、原始身份信息或完整对话。

## 技术栈

- 前端：Vue 3 + Vite + TypeScript + Vue Router + Pinia + Element Plus
- 3D 与图表：Three.js + `@pixiv/three-vrm` + ECharts
- 后端：FastAPI + SQLAlchemy + Alembic + JWT + bcrypt
- 数据库与检索：PostgreSQL + pgvector；测试环境使用 SQLite
- AI 服务：阿里云百炼/通义千问（LLM、Embedding、Rerank、ASR、TTS），可配置火山引擎实时 TTS

## 目录结构

```text
.
├── backend/      # FastAPI 后端
├── frontend/     # Vue3 前端
├── docs/         # 接口和开发文档
├── scripts/      # 数据库、前后端和报告 worker 脚本
└── docker-compose.yml
```

## 快速启动

推荐在 Windows PowerShell 中运行，并确保已安装 Python、Node.js、Docker Desktop 和 `ffmpeg`。`ffmpeg` 用于把浏览器录音转换成 ASR 所需的 16 kHz 单声道 WAV。

1. 复制本地环境变量文件：

   ```powershell
   Copy-Item backend\.env.example backend\.env
   Copy-Item frontend\.env.example frontend\.env
   ```

   然后按本机情况修改 `backend/.env`：

   - `DATABASE_URL`：PostgreSQL 用户名、密码、端口和数据库名
   - `SECRET_KEY`：本地 JWT 密钥，协作者各自生成一串长随机值即可
   - `DASHSCOPE_API_KEY`、`DASHSCOPE_API_HOST`、`LLM_BASE_URL`、`DASHSCOPE_BASE_URL`：阿里云百炼/通义千问配置
   - `VOLCENGINE_TTS_API_KEY`：火山引擎实时语音 API Key，仅写入本地 `backend/.env`

   `frontend/.env` 默认使用相对地址 `VITE_API_BASE_URL=/api`。开发服务器会把 `/api` 代理到 `VITE_API_PROXY_TARGET`，未设置时目标为 `http://localhost:8000`。`VITE_API_PROXY_TARGET` 当前需在启动前端的 PowerShell 终端中设置，不要只写入 `frontend/.env`。

2. 启动本地 pgvector PostgreSQL：

   ```powershell
   .\scripts\start-pgvector.ps1
   ```

   脚本会复用 `backend/.env` 中的数据库账号、密码、库名和首选端口。若端口已被占用，会在 `5433-5450` 中选择空闲端口，并写入被 Git 忽略的 `backend/.env.docker`，后端和 Alembic 会自动使用实际端口。数据库数据保存在 `.local-data/pgvector-postgres/`，不会提交 Git。首次启动前请确认 Docker Desktop 已运行。

3. 安装并初始化后端：

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   alembic upgrade head
   $env:INITIAL_ADMIN_PASSWORD = Read-Host "请输入至少 12 位的管理员初始密码"
   python scripts\init_admin.py
   ```

   如果本机策略不允许创建 `.venv`，可以改用项目内依赖目录：

   ```powershell
   cd backend
   python -m pip install -r requirements.txt --target .python-packages
   $env:PYTHONPATH=(Join-Path (Get-Location) ".python-packages")
   python -m alembic upgrade head
   $env:INITIAL_ADMIN_PASSWORD = Read-Host "请输入至少 12 位的管理员初始密码"
   python scripts\init_admin.py
   ```

   自动生成游客感受度日报/周报时，从仓库根目录另开一个终端运行：

   ```powershell
   if (Test-Path .\backend\.venv\Scripts\Activate.ps1) {
     . .\backend\.venv\Scripts\Activate.ps1
   }
   .\scripts\dev-report-worker.ps1
   ```

   正式部署需将该 worker 作为独立常驻进程运行；Web API 本身不会在多进程环境中重复执行定时任务。

4. 首次启动前端前安装依赖：

   ```powershell
   cd frontend
   npm.cmd install
   cd ..
   ```

   然后从仓库根目录分别启动后端和前端。如果使用 `.venv`，终端 A 必须先激活它；如果使用 `.python-packages`，后端脚本会自动配置 `PYTHONPATH`。

   ```powershell
   # 终端 A
   if (Test-Path .\backend\.venv\Scripts\Activate.ps1) {
     . .\backend\.venv\Scripts\Activate.ps1
   }
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev-backend.ps1

   # 终端 B
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev-frontend.ps1
   ```

5. 通过 HTTP 验证：

   - 前端：http://localhost:5173
   - 后端健康检查：http://localhost:8000/api/health
   - 后端文档：http://localhost:8000/docs

   Vite 在 `5173` 被占用时会提示实际使用的下一个端口。后端默认不会自动换端口；若 `8000` 已被其他程序占用，可在已激活 `.venv` 或已设置 `PYTHONPATH` 的后端终端运行：

   ```powershell
   cd backend
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
   ```

   同时在前端启动终端中设置代理目标：

   ```powershell
   cd frontend
   $env:VITE_API_PROXY_TARGET='http://127.0.0.1:8010'
   npm.cmd run dev -- --host 127.0.0.1 --port 5180 --strictPort
   ```

管理员用户名默认是 `admin`，初始密码必须通过 `INITIAL_ADMIN_PASSWORD` 配置为至少 12 位的强密码。初始化脚本只会在管理员不存在时创建账号；重复执行不会重置已有管理员密码。

### 可选：导入示范景区业务数据

迁移只创建数据库结构和基础景区，不会自动导入完整景点与游客行为数据。取得官方“示范景区公开资料包”后，可执行幂等导入；资料包需包含 `灵山胜境 景点结构化数据集.docx` 和 `景点景区旅游数据行为分析数据.xlsx`：

```powershell
cd backend
python scripts/import_scenic_package.py --package-dir 'C:\path\to\示范景区公开资料包'
```

知识文档及其 Embedding 需在管理端“知识库管理”中上传并完成索引。官方资料包不随 Git 仓库分发；未导入时系统仍可启动，但景点、路线与 RAG 演示内容不完整。

## 数字人素材恢复

仓库已包含 10 个比赛用 VRM 及 `backend/uploads/avatars/manifest.json`。迁移完成后可校验并幂等导入：

```powershell
cd backend
python scripts/seed_avatars.py --verify-only
python scripts/seed_avatars.py
```

校验会检查 GLB 文件头、文件大小和 SHA-256；任一文件缺失或被篡改时不会写入数据库。数字人动作文件位于 `frontend/public/animations/`，前端构建会复制到产物目录。

## pgvector

本项目使用 `pgvector/pgvector` Docker 镜像，迁移会执行 `CREATE EXTENSION IF NOT EXISTS vector`。保持 `RAG_VECTOR_BACKEND=pgvector` 时由数据库计算余弦距离；临时切换为 `json` 时由应用计算。两种模式共用同一份向量数据，无需重新建表或重建索引。不要将 PostgreSQL 数据目录、真实密码或 API Key 提交到 Git。

## 测试与构建

```powershell
cd backend
pip install -r requirements-dev.txt
pytest
```

测试默认使用 SQLite，不会写入本地 PostgreSQL。前端生产构建：

```powershell
cd frontend
npm.cmd run build
```

构建完成后，重启 FastAPI；它会在启动时检测 `frontend/dist/index.html`，并同时托管前端页面、静态资源和 `/api`，可用于单端口演示。

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
LLM_RERANK_MODEL=qwen3-rerank
RAG_VECTOR_BACKEND=pgvector
GUIDE_ASR_MODEL=qwen3-asr-flash
GUIDE_TTS_MODEL=qwen3-tts-instruct-flash
INSIGHT_ANALYSIS_MODEL=qwen-plus
INSIGHT_REPORT_MODEL=qwen-plus
```

若启用火山引擎实时语音，还需在本地配置 `VOLCENGINE_TTS_API_KEY` 和相应音色选项。所有真实 API Key 只写入 `backend/.env`，不要写入 `.env.example`、README、日志或提交信息。
