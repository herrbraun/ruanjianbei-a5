# 开发说明

## 第一阶段边界

当前骨架只实现登录、鉴权、路由和数据库基础表。暂不实现 RAG、数字人、语音、知识库管理和大屏业务。

## 模型配置

默认使用阿里云百炼/通义千问作为国内模型供应商：

```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_API_HOST=your-workspace.cn-beijing.maas.aliyuncs.com
LLM_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
DASHSCOPE_BASE_URL=https://your-workspace.cn-beijing.maas.aliyuncs.com/api/v1
LLM_CHAT_MODEL=qwen-plus
LLM_EMBEDDING_MODEL=text-embedding-v4
LLM_RERANK_MODEL=qwen3-rerank
ASR_MODEL=fun-asr
TTS_MODEL=cosyvoice-v3.5-plus
```

真实 API Key 只写入 `backend/.env`，不要提交到 Git。

## 分工建议

- `feature/visitor`：游客端、数字人展示、语音输入、TTS 播放、路线推荐。
- `feature/admin-backend`：后端业务接口、RAG、知识库、管理后台数据分析。

接口变更需要同步更新 `docs/API.md`。

## 常用命令

首次拉库后先复制本地环境变量文件：

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

再按本机 PostgreSQL 密码和阿里云百炼 API Key 修改 `backend/.env`。真实密钥只保存在本地 `.env`，不要提交到 Git。

本地 pgvector PostgreSQL：

```powershell
.\scripts\start-pgvector.ps1
```

脚本使用 `backend/.env` 的数据库账号、密码、库名和首选端口，数据保存在项目 `.local-data/pgvector-postgres/`。若首选端口被占用，脚本会自动选择 `5433-5450` 中的空闲端口，并写入被 Git 忽略的 `backend/.env.docker`；后端和 Alembic 会自动使用该端口。

后端：

```powershell
cd backend
alembic upgrade head
python scripts\init_admin.py
uvicorn app.main:app --reload
```

认证测试：

```powershell
cd backend
pip install -r requirements-dev.txt
pytest
```

测试使用内存 SQLite，不会写入本地 PostgreSQL。

协作者也可以用 SQL 文件直接初始化数据库：

```powershell
psql -h localhost -p 5432 -U postgres -d ai_tour_guide -f backend/sql/init_auth_schema.sql
```

### 游客语音导览依赖

游客语音输入使用本机 `ffmpeg` 将浏览器录音转为 16 kHz 单声道 WAV，再调用百炼 ASR；启动前执行 `ffmpeg -version` 确认可用。若可执行文件不在 `PATH`，在本地 `backend/.env` 设置 `MEDIA_FFMPEG_BINARY` 为其完整路径。真实密钥只保留在被忽略的本地 `.env` 中。

前端：

```powershell
cd frontend
npm.cmd run dev
npm.cmd run build
```
