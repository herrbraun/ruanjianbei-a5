# 开发说明

## 数字人本地素材

管理员可从“数字人形象管理”上传 `.vrm`。模型保存在 `backend/uploads/avatars/`；比赛使用的自制 `.vrm` 会纳入版本控制，知识库原文件和游客头像仍保持忽略。上传限制为 80MB，服务端会检查 `.vrm` 后缀和 GLB `glTF` 文件头。

执行迁移后，可用以下命令把十个自制灵山讲解员导入默认灵山景区：

```powershell
cd backend
python scripts\seed_avatars.py --source "$HOME\Documents" --scenic-code lingshan
```

可在本地 `backend/.env` 配置音色白名单和上传上限；不要把真实密钥写进示例文件：

```env
GUIDE_TTS_VOICE_OPTIONS=Cherry
AVATAR_MAX_UPLOAD_BYTES=83886080
```

游客端用 Three.js 与 `@pixiv/three-vrm` 渲染 VRM，并用 TTS 音频的 `AnalyserNode` 音量驱动 `aa` 嘴型；模型或 WebGL 不可用时会保留文字与语音讲解并显示静态卡片。

## 当前实现范围

当前已覆盖登录鉴权、景点与路线、RAG 知识库、文字/语音导览、数字人展示与配置、游客会话评价、互动感受度分析、管理数据大屏和日报/周报。互动分析由问答请求创建待处理记录，再由后台任务调用模型；管理端聚合查询只读取结构化结果，不在大屏请求中实时调用模型。

游客端不再展示注册或登录页。访问游客功能时前端通过 `/auth/guest-session` 自动创建或恢复匿名游客；恢复密钥只保存在浏览器，管理员仍使用独立账号登录。开发调试游客接口时，应先调用匿名会话接口取得 Bearer Token。

路线结果可从首站或任意站进入数字人导览。导览会话持久化 `route_plan_id` 与 `current_spot_id`，游客端提供上一站、下一站、讲解当前站和继续导览；RAG 检索及回答提示词会结合当前景点、路线兴趣和完整行程。路线与景点上下文更新必须通过归属校验，不能绑定其他游客或其他景区的路线。

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
RAG_VECTOR_BACKEND=pgvector
RAG_JSON_CANDIDATE_LIMIT=2000
ASR_MODEL=fun-asr
TTS_MODEL=cosyvoice-v3.5-plus
INSIGHT_ANALYSIS_MODEL=qwen-plus
INSIGHT_REPORT_MODEL=qwen-plus
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
$env:INITIAL_ADMIN_PASSWORD = Read-Host "请输入至少 12 位的管理员初始密码"
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

## 景点与路线数据

开发者 B 模块包含景点、标签、景点素材、路线方案、路线景点、路线反馈、推荐设置和游客行为记录。新数据库执行 `alembic upgrade head` 即可创建完整结构；真实资料通过以下脚本导入：

```powershell
cd backend
python scripts\import_scenic_package.py
python scripts\import_spot_images.py
```

导入脚本按景点名称关联素材，无法匹配的文件不会写入数据库。前端和后端验证命令：

```powershell
cd backend
python -m compileall app

cd ..\frontend
npm.cmd run build
```
