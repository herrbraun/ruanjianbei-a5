# 已有功能缺陷修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复当前已经实现功能中的权限、超时、跨景区路线、管理员初始化、动作资源路径和语音上传限制问题，不扩展尚未完成的产品能力。

**Architecture:** 保持现有 Vue + FastAPI + SQLAlchemy 分层。后端权限修复通过受控媒体路由替代整个上传目录静态挂载；路线继续使用当前 `scenic_area` 字符串模型，但在请求、存储和查询中强制限定单一景区；前端只为耗时 AI 接口覆盖超时配置。

**Tech Stack:** Vue 3、TypeScript、Axios、FastAPI、SQLAlchemy、Alembic、PostgreSQL、pytest、Vite。

## Global Constraints

- 10 个自制 VRM 和 4 个比赛展示动作按用户后续要求纳入项目仓库；知识库原文件和游客头像继续保持忽略。
- 不新增 OSS/S3、Redis、声音复刻、音素级口型或新的数字人制作能力。
- 不改变现有游客/管理员角色体系和 JWT 格式。
- 数据库结构变化必须同时更新 Alembic 与 `backend/sql/init_auth_schema.sql`。
- 每个任务单独提交；提交前运行后端无缓存测试和前端生产构建。

---

### Task 1: 收紧上传文件访问边界

**Files:**
- Create: `backend/app/routers/media.py`
- Modify: `backend/app/main.py:3-51`
- Modify: `backend/app/routers/__init__.py`
- Test: `backend/tests/test_media_access.py`

**Interfaces:**
- Produces: `GET /uploads/avatars/{filename}`，只允许读取 `user-<id>-<uuid>.(png|jpg|webp)` 用户头像。
- Preserves: 数据库已有 `/uploads/avatars/<filename>` 头像 URL 无需迁移。
- Removes: 对 `backend/uploads` 整棵目录的匿名静态访问。

- [ ] **Step 1: 写权限回归测试**

在 `backend/tests/test_media_access.py` 创建临时上传目录并覆盖媒体模块路径，验证合法用户头像为 200，而 VRM 和知识库文件均为 404：

```python
def test_only_user_avatar_files_are_public(client, tmp_path, monkeypatch):
    avatar_dir = tmp_path / "avatars"
    avatar_dir.mkdir()
    (avatar_dir / "user-1-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (avatar_dir / "secret.vrm").write_bytes(b"glTF")
    monkeypatch.setattr("app.routers.media.USER_AVATAR_DIRECTORY", avatar_dir)

    assert client.get("/uploads/avatars/user-1-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png").status_code == 200
    assert client.get("/uploads/avatars/secret.vrm").status_code == 404
    assert client.get("/uploads/knowledge/document.pdf").status_code == 404
```

- [ ] **Step 2: 确认测试先失败**

Run:

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m pytest -q -p no:cacheprovider tests/test_media_access.py
```

Expected: VRM 或知识库文件仍可通过 `/uploads` 访问，测试失败。

- [ ] **Step 3: 实现受控头像媒体路由**

`backend/app/routers/media.py` 使用严格正则和 basename 校验：

```python
from pathlib import Path
import re

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

router = APIRouter(tags=["media"])
USER_AVATAR_DIRECTORY = Path(__file__).resolve().parents[2] / "uploads" / "avatars"
USER_AVATAR_PATTERN = re.compile(r"^user-\d+-[0-9a-f]{32}\.(?:png|jpg|webp)$")

@router.get("/uploads/avatars/{filename}", include_in_schema=False)
def read_user_avatar(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    if safe_name != filename or not USER_AVATAR_PATTERN.fullmatch(safe_name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    path = USER_AVATAR_DIRECTORY / safe_name
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
```

在 `main.py` 注册 `media.router`，并删除 `app.mount("/uploads", ...)`；保留 `/static`、`/assets` 和 `/animations`。

- [ ] **Step 4: 验证权限与现有头像兼容**

Run:

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m pytest -q -p no:cacheprovider tests/test_media_access.py tests/test_avatar_routes.py tests/test_auth.py
```

Expected: 全部通过；停用 VRM 仍只能通过带鉴权的数字人 asset API 读取。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/main.py backend/app/routers/media.py backend/app/routers/__init__.py backend/tests/test_media_access.py
git commit -m "fix: restrict uploaded media access"
```

---

### Task 2: 为 AI 导览接口配置合理超时

**Files:**
- Modify: `frontend/src/api/guide.ts:54-69`
- Modify: `frontend/src/api/http.ts:12-15`
- Create: `frontend/src/api/timeouts.ts`

**Interfaces:**
- Produces: `DEFAULT_API_TIMEOUT_MS = 10_000`、`AI_API_TIMEOUT_MS = 120_000`。
- Applies: 问答、ASR、TTS 使用 120 秒；普通 CRUD 继续使用 10 秒。

- [ ] **Step 1: 提取明确的超时常量**

创建 `frontend/src/api/timeouts.ts`：

```ts
export const DEFAULT_API_TIMEOUT_MS = 10_000
export const AI_API_TIMEOUT_MS = 120_000
```

在 `http.ts` 用 `DEFAULT_API_TIMEOUT_MS` 替换裸数字 `10000`。

- [ ] **Step 2: 为三类耗时接口覆盖超时**

将 `guide.ts` 的实现调整为：

```ts
sendMessage: (sessionId, content, inputMode) =>
  http.post<GuideConversationResponse>(
    `/guide/sessions/${sessionId}/messages`,
    { content, input_mode: inputMode },
    { timeout: AI_API_TIMEOUT_MS },
  ),
transcribe: (file) => {
  const form = new FormData()
  form.append('file', file, 'guide-recording.webm')
  return http.post<AsrResult>('/guide/asr', form, { timeout: AI_API_TIMEOUT_MS })
},
synthesize: (messageId, avatarVariantId) =>
  http.post<Blob>(`/guide/messages/${messageId}/speech`, undefined, {
    params: avatarVariantId ? { avatar_variant_id: avatarVariantId } : undefined,
    responseType: 'blob',
    timeout: AI_API_TIMEOUT_MS,
  }),
```

- [ ] **Step 3: 运行类型检查和构建**

Run:

```powershell
cd frontend
npx.cmd vue-tsc --noEmit
npm.cmd run build
```

Expected: 类型检查和构建均成功；普通接口仍保持 10 秒超时。

- [ ] **Step 4: 提交**

```powershell
git add frontend/src/api/http.ts frontend/src/api/guide.ts frontend/src/api/timeouts.ts
git commit -m "fix: extend timeouts for guide ai requests"
```

---

### Task 3: 路线推荐强制限定单一景区

**Files:**
- Modify: `backend/app/models/spot.py`
- Modify: `backend/app/schemas/routes.py:8-37`
- Modify: `backend/app/crud/routes.py:96-165`
- Modify: `backend/app/routers/routes.py`
- Create: `backend/alembic/versions/202607160001_scope_routes_to_scenic_area.py`
- Modify: `backend/sql/init_auth_schema.sql`
- Modify: `frontend/src/api/routes.ts`
- Modify: `frontend/src/views/RouteRecommendView.vue`
- Create: `backend/tests/test_routes.py`

**Interfaces:**
- Adds: `RouteRecommendRequest.scenic_area: str`。
- Adds: `RoutePlan.scenic_area: str` 和 `RoutePlanResponse.scenic_area: str`。
- Guarantees: 推荐结果和可选起点全部来自所选景区。

- [ ] **Step 1: 写跨景区回归测试**

在 `backend/tests/test_routes.py` 创建两个景区的启用景点，提交 `scenic_area="灵山胜境"`，断言结果只包含该景区景点；把另一个景区景点作为 `start_spot_id` 时断言 400：

```python
def test_recommendation_never_mixes_scenic_areas(visitor_client, route_spots):
    response = visitor_client.post("/api/routes/recommend", json={
        "scenic_area": "灵山胜境",
        "interest": "文化",
        "duration_minutes": 120,
        "preference": "balanced",
    })
    assert response.status_code == 201
    assert response.json()["scenic_area"] == "灵山胜境"
    assert {item["spot_id"] for item in response.json()["spots"]}.isdisjoint(route_spots["nianhuawan_ids"])
```

- [ ] **Step 2: 确认测试先失败**

Run:

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m pytest -q -p no:cacheprovider tests/test_routes.py
```

Expected: 请求结构或跨景区断言失败。

- [ ] **Step 3: 增加模型、Schema 和迁移**

给 `RoutePlan` 增加：

```python
scenic_area: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
```

给请求和响应增加：

```python
scenic_area: str = Field(min_length=1, max_length=120)
```

迁移对已有路线用起点或第一站景点回填 `scenic_area`，无法回填时写入 `"未指定景区"`，随后设置非空并建立索引。同步更新初始化 SQL。

- [ ] **Step 4: 后端查询限定景区**

在 `recommend_route` 构造查询时增加：

```python
scenic_area = payload.scenic_area.strip()
stmt = stmt.where(ScenicSpot.scenic_area == scenic_area)
```

创建 `RoutePlan` 时写入 `scenic_area=scenic_area`。这样跨景区起点不会出现在 `spots` 中，沿用现有“起点不可用”错误即可。

- [ ] **Step 5: 前端增加景区选择并过滤起点**

在 `RouteRecommendView.vue` 从已加载景点生成景区选项：

```ts
const scenicAreas = computed(() => [...new Set(spots.value.map((spot) => spot.scenic_area))])
const availableStartSpots = computed(() => spots.value.filter((spot) => spot.scenic_area === form.scenic_area))
```

景区变化时清空 `start_spot_id`；提交载荷增加 `scenic_area`。起点下拉改用 `availableStartSpots`。

- [ ] **Step 6: 验证迁移、接口和前端**

Run:

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m alembic heads
python -m pytest -q -p no:cacheprovider tests/test_routes.py
cd ..\frontend
npm.cmd run build
```

Expected: 一个 Alembic head；路线测试和前端构建通过。

- [ ] **Step 7: 提交**

```powershell
git add backend/app/models/spot.py backend/app/schemas/routes.py backend/app/crud/routes.py backend/app/routers/routes.py backend/alembic/versions/202607160001_scope_routes_to_scenic_area.py backend/sql/init_auth_schema.sql backend/tests/test_routes.py frontend/src/api/routes.ts frontend/src/views/RouteRecommendView.vue
git commit -m "fix: scope route recommendations to one scenic area"
```

---

### Task 4: 移除固定管理员初始密码

**Files:**
- Modify: `backend/scripts/init_admin.py`
- Modify: `backend/.env.example`
- Modify: `README.md`
- Modify: `docs/DEVELOPMENT.md`
- Create: `backend/tests/test_init_admin.py`

**Interfaces:**
- Consumes: `INITIAL_ADMIN_USERNAME`，默认 `admin`。
- Requires: `INITIAL_ADMIN_PASSWORD`，至少 12 字符且不能是 `123456`、`password` 或 `admin123456`。

- [ ] **Step 1: 写凭据校验测试**

把凭据读取提取为 `read_initial_admin_credentials() -> tuple[str, str]`，测试缺失密码和弱密码抛出 `RuntimeError`，强密码被原样返回。

- [ ] **Step 2: 实现安全初始化**

`init_admin.py` 使用：

```python
def read_initial_admin_credentials() -> tuple[str, str]:
    username = os.getenv("INITIAL_ADMIN_USERNAME", "admin").strip()
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    weak = {"123456", "password", "admin123456"}
    if len(password) < 12 or password.lower() in weak:
        raise RuntimeError("请通过 INITIAL_ADMIN_PASSWORD 配置至少 12 位的管理员初始密码")
    return username, password
```

不得打印密码，只输出管理员用户名和创建结果。管理员已存在时保持幂等，不重置密码。

- [ ] **Step 3: 更新示例配置和文档**

`.env.example` 只写占位值：

```env
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=replace-with-a-strong-admin-password
```

删除 README 和开发文档中所有 `admin / 123456` 的操作指引。

- [ ] **Step 4: 验证**

Run:

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m pytest -q -p no:cacheprovider tests/test_init_admin.py tests/test_auth.py
```

Expected: 测试通过；没有环境密码时脚本明确失败且不会创建弱密码管理员。

- [ ] **Step 5: 提交**

```powershell
git add backend/scripts/init_admin.py backend/.env.example README.md docs/DEVELOPMENT.md backend/tests/test_init_admin.py
git commit -m "fix: require secure initial admin credentials"
```

---

### Task 5: 统一数字人动作的开发与生产路径

**Files:**
- Modify: `frontend/src/components/AvatarViewer.vue:15-21`
- Modify: `frontend/scripts/copy-avatar-animations.mjs:6-12`
- Modify: `backend/app/main.py:42-56`
- Modify: `docs/ASSET_ATTRIBUTION.md:23-26`

**Interfaces:**
- Standardizes: 所有环境统一通过 `/animations/...` 读取 VRMA。
- Build output: `frontend/dist/animations`。

- [ ] **Step 1: 修改动作 URL**

将动作表改为：

```ts
const ANIMATION_ASSETS = {
  idle: { url: '/animations/chatvrm-idle-loop.vrma', loop: true },
  welcome: { url: '/animations/mixamo/welcome-wave.vrma', loop: false },
  guiding: { url: '/animations/mixamo/guide-point.vrma', loop: false },
  thinking: { url: '/animations/mixamo/thinking.vrma', loop: true },
  speaking: { url: '/animations/mixamo/speaking.vrma', loop: true },
}
```

- [ ] **Step 2: 修改构建复制目标**

`copy-avatar-animations.mjs` 默认输出改为 `../dist/animations`。FastAPI 已有 `/animations` 挂载逻辑，保留并验证目录存在。

- [ ] **Step 3: 构建并检查资源**

Run:

```powershell
cd frontend
npm.cmd run build
Test-Path dist\animations\chatvrm-idle-loop.vrma
```

Expected: 构建成功，`Test-Path` 返回 `True`。若本机 Mixamo 文件存在，四个 `dist/animations/mixamo/*.vrma` 也应存在。

- [ ] **Step 4: 提交**

```powershell
git add frontend/src/components/AvatarViewer.vue frontend/scripts/copy-avatar-animations.mjs backend/app/main.py docs/ASSET_ATTRIBUTION.md
git commit -m "fix: unify avatar animation asset paths"
```

---

### Task 6: 在读取前限制 ASR 上传大小

**Files:**
- Modify: `backend/app/routers/guide.py:170-186`
- Test: `backend/tests/test_guide_routes.py`

**Interfaces:**
- Enforces: 原始音频超过 `settings.guide_max_audio_bytes` 返回 HTTP 413。
- Preserves: 合法音频继续交给 `recognize_speech` 做格式转换和内容校验。

- [ ] **Step 1: 写超限测试**

```python
def test_asr_rejects_oversized_upload_before_transcoding(visitor_client, monkeypatch):
    monkeypatch.setattr(settings, "guide_max_audio_bytes", 8)
    response = visitor_client.post(
        "/api/guide/asr",
        files={"file": ("recording.webm", b"123456789", "audio/webm")},
    )
    assert response.status_code == 413
```

- [ ] **Step 2: 使用上限加一读取**

将路由读取改为：

```python
try:
    audio = await file.read(settings.guide_max_audio_bytes + 1)
finally:
    await file.close()
if len(audio) > settings.guide_max_audio_bytes:
    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="录音文件不能超过 6 MB")
```

MIME 类型校验也放入会执行 `file.close()` 的控制流中。

- [ ] **Step 3: 验证语音回归**

Run:

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m pytest -q -p no:cacheprovider tests/test_guide_routes.py tests/test_speech.py
```

Expected: 全部通过；超限请求不调用 ffmpeg 或 DashScope。

- [ ] **Step 4: 提交**

```powershell
git add backend/app/routers/guide.py backend/tests/test_guide_routes.py
git commit -m "fix: cap guide audio uploads before buffering"
```

---

### Task 7: 全量回归和交付检查

**Files:**
- Modify only if verification exposes a regression in Tasks 1-6.

- [ ] **Step 1: 后端全量测试**

Run:

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m pytest -q -p no:cacheprovider
```

Expected: 现有 22 个测试和新增测试全部通过。`-p no:cacheprovider` 仅用于当前受限执行环境，避免 pytest 缓存目录写入卡住。

- [ ] **Step 2: 检查迁移图和应用导入**

Run:

```powershell
python -m alembic heads
python -c "from app.main import app; print(len(app.routes))"
```

Expected: 只有一个 Alembic head，应用成功导入。

- [ ] **Step 3: 前端生产构建**

Run:

```powershell
cd ..\frontend
npm.cmd run build
```

Expected: TypeScript 与 Vite 构建成功，动作被复制到 `dist/animations`。

- [ ] **Step 4: 安全回归检查**

启动本地服务后验证：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/uploads/knowledge/test.pdf -TimeoutSec 5
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/uploads/avatars/test.vrm -TimeoutSec 5
```

Expected: 两个请求均返回 404；已上架 VRM 通过带 Bearer Token 的 `/api/avatars/scenic-areas/.../asset` 返回 200。

- [ ] **Step 5: 检查工作区与敏感信息**

Run:

```powershell
git status --short --ignored
git diff --check
git grep -n -E "admin / 123456|INITIAL_ADMIN_PASSWORD=123456|sk-[A-Za-z0-9]"
```

Expected: `.env`、上传文件、Mixamo 文件和构建产物均未暂存；无真实密钥或弱管理员密码进入提交。
