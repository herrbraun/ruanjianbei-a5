# 功能需求与两名全栈开发分工

本文按“功能闭环”拆分需求。两名开发者都是全栈，不按前端/后端分工；每个人独立负责某一组功能从数据库、接口、服务逻辑到页面交互的完整实现。

## 分工原则

- 按业务功能包分工，不按技术层分工。
- 每个功能包都必须能独立演示：有表结构、有接口、有页面、有数据、有验收流程。
- 谁负责一个功能，谁就负责该功能需要的前端、后端、数据库迁移、初始化数据、接口文档和验证。
- 如果某个功能依赖前置能力，前置能力应纳入同一功能包的最小闭环。例如“数字导览”依赖知识检索，那么 RAG 的最小实现就属于数字导览功能包。
- 共用能力只保留在公共层：登录、JWT、用户身份、基础布局、环境变量、通用 HTTP 客户端。

## 已有公共底座

- 游客登录、管理员登录、当前用户接口。
- JWT 鉴权和前端角色路由守卫。
- `users`、`visitor_profiles`、`admin_profiles`、`login_logs` 基础表。
- `/login`、`/visitor`、`/admin` 占位页面。
- PostgreSQL、Alembic、SQL 初始化脚本、前后端 `.env.example`。

后续两个人开发时都复用这个公共底座，不再重复做登录。

## 开发者 A：智能数字导览闭环

### 功能目标

完成游客端最核心的“问问题 -> 检索景区知识 -> 大模型生成回答 -> 数字人/文本/语音播报”的完整闭环。

这个功能包不只是游客页面，也包括它需要的后端能力：知识库最小管理、RAG 检索、模型调用、导览会话、消息记录、数字人状态和语音能力。

### 包含功能

1. 知识库最小闭环
   - 管理员或开发者可以上传/录入景区知识资料。
   - 系统可以把资料切分成 chunk。
   - 系统可以生成 embedding 并建立向量检索。
   - 检索结果能带来源信息。

2. RAG 检索
   - 游客提问后，先从知识库召回相关内容。
   - 支持按景点、兴趣标签或文档来源做基础过滤。
   - 记录检索日志，便于后续统计命中率和问题热度。

3. 导览对话
   - 建立游客导览会话。
   - 保存游客问题、RAG 上下文、模型回答和引用来源。
   - 支持连续对话，刷新后可以恢复当前会话或历史消息。
   - 模型失败、RAG 无结果、网络超时时要有明确降级提示。

4. 游客端数字导览页面
   - 在游客页提供导览问答入口。
   - 展示数字人形象或数字人占位形象。
   - 数字人至少有待机、聆听、思考、播报、错误几种状态。
   - 回答展示要包含正文和资料来源。
   - 提供推荐问题，例如“这个景点有什么历史？”、“适合亲子游吗？”。

5. 语音导览
   - 第一版可以先做 TTS 播放文本回答。
   - 有余力再做 ASR 语音提问。
   - 文本问答和语音问答共用同一套导览会话。

### 建议后端数据表

- `knowledge_documents`：知识文档，记录标题、类型、来源、状态、上传人。
- `knowledge_chunks`：切分后的知识片段，记录文档 ID、内容、序号、元数据。
- `knowledge_embeddings`：chunk 向量，记录模型名、向量数据、生成时间。
- `rag_query_logs`：RAG 检索日志，记录问题、召回结果、耗时、用户 ID。
- `guide_sessions`：游客导览会话，记录游客 ID、兴趣、当前景点、创建时间。
- `guide_messages`：会话消息，记录角色、内容、引用来源、模型名、耗时。
- `tts_assets`：TTS 音频资源，记录消息 ID、音频地址、生成状态。

### 建议接口

- `POST /api/admin/knowledge/documents`：新增或上传知识资料。
- `GET /api/admin/knowledge/documents`：知识资料列表。
- `POST /api/admin/knowledge/documents/{id}/index`：解析并索引文档。
- `POST /api/rag/search`：RAG 检索。
- `POST /api/guide/sessions`：创建导览会话。
- `GET /api/guide/sessions/{id}/messages`：获取会话消息。
- `POST /api/guide/chat`：文本导览问答。
- `POST /api/voice/tts`：生成回答语音。
- `POST /api/voice/asr`：语音识别，可作为第二阶段。

### 建议前端页面与组件

- `/visitor/guide` 或游客首页导览区域。
- 导览聊天面板。
- 数字人展示组件。
- RAG 来源展示组件。
- 推荐问题组件。
- TTS 播放控件。
- 知识资料最小管理入口，可以先放在 `/admin/knowledge`。

### 验收标准

- 管理员能录入一份景区介绍资料并完成索引。
- 游客登录后能提问并得到基于资料的回答。
- 回答能展示引用来源。
- 系统能保存并恢复导览会话。
- 数字人状态会随提问、思考、回答、错误变化。
- TTS 第一版能播放回答音频；如果 ASR 未完成，页面仍可用文本输入。
- 前端构建通过，后端导入和主要接口可用。

## 开发者 B：景区服务与运营管理闭环

### 功能目标

完成“景区基础数据 -> 路线推荐 -> 管理后台维护 -> 运营统计展示”的完整闭环。

这个功能包同样是全栈：包括景点/服务点数据模型、管理员维护页面、游客路线推荐页面、推荐接口、反馈记录和后台统计大屏。

### 包含功能

1. 景区基础数据
   - 建立景点、展区、服务点、标签、开放时间、推荐时长等基础数据。
   - 支持管理员新增、编辑、启停。
   - 支持游客端读取景点列表和详情。

2. 素材与内容资产
   - 管理景点封面图、介绍图、视频或音频地址。
   - 记录素材绑定对象和描述。
   - 第一版可以只保存 URL，不必做复杂文件存储。

3. 路线推荐
   - 游客可以选择兴趣、游玩时长、起点或偏好。
   - 系统根据景点标签、推荐时长和优先级生成路线。
   - 路线包含景点顺序、预计耗时、推荐理由。
   - 游客可以提交路线反馈。

4. 游客端路线页面
   - 展示推荐路线。
   - 展示每个景点的简介、顺序、预计停留时间。
   - 点击景点可以查看详情。
   - 后续可以与 A 的导览对话联动，例如“让数字导游讲解这个景点”。

5. 管理后台
   - 景点管理页面。
   - 素材管理页面。
   - 路线推荐规则或权重配置页面。
   - 运营统计页面。

6. 运营统计
   - 统计游客登录次数。
   - 统计路线推荐次数和路线反馈。
   - 统计热门景点、热门兴趣标签。
   - 可以读取 A 功能包产生的问答日志，但不要阻塞本功能包第一版。

### 建议后端数据表

- `scenic_spots`：景点/展区/服务点基础信息。
- `spot_tags`：景点标签。
- `spot_media_assets`：景点素材。
- `route_plans`：游客生成的路线方案。
- `route_spots`：路线中的景点顺序和停留时间。
- `route_feedback`：路线满意度和反馈。
- `operation_daily_stats`：按天聚合的运营数据，可第二阶段再做。

### 建议接口

- `GET /api/spots`：游客端景点列表。
- `GET /api/spots/{id}`：游客端景点详情。
- `GET /api/admin/spots`：管理端景点列表。
- `POST /api/admin/spots`：新增景点。
- `PUT /api/admin/spots/{id}`：编辑景点。
- `PATCH /api/admin/spots/{id}/status`：启停景点。
- `POST /api/routes/recommend`：生成推荐路线。
- `GET /api/routes/{id}`：路线详情。
- `POST /api/routes/{id}/feedback`：路线反馈。
- `GET /api/admin/analytics/overview`：后台统计概览。
- `GET /api/admin/analytics/routes`：路线统计。
- `GET /api/admin/analytics/spots`：景点统计。

### 建议前端页面与组件

- `/visitor/routes`：游客路线推荐页。
- `/visitor/spots`：游客景点列表页。
- `/visitor/spots/:id`：游客景点详情页。
- `/admin/spots`：管理端景点管理。
- `/admin/media`：素材管理，可第二阶段。
- `/admin/routes`：路线数据和反馈管理。
- `/admin/analytics`：运营统计页面。

### 验收标准

- 管理员能新增、编辑、启停景点。
- 游客能查看景点列表和详情。
- 游客选择兴趣和时长后能得到一条路线。
- 路线包含景点顺序、预计耗时和推荐理由。
- 游客能提交路线反馈。
- 管理员能看到登录、路线推荐、热门景点等基础统计。
- 管理端接口游客无法访问。
- 前端构建通过，后端导入和主要接口可用。

### 当前实现核查（2026-07-10）

- B 的景区基础数据、素材 URL 管理、路线推荐、游客路线页、反馈、路线管理和运营统计均已完成。
- 真实景点与游客行为数据通过 `backend/scripts/import_scenic_package.py` 幂等导入，不使用 mock 数据或占位素材 URL。
- A 的问答日志接入、路线到数字导览的联动仍等待 A 提供对应数据表和前端路由；两项均不阻塞 B 独立验收。

## 公共协作边界

### 两个人都可以改的公共区域

- 登录态展示和基础布局。
- `frontend/src/api/http.ts` 的通用请求能力。
- `backend/app/core/security.py` 的通用认证能力。
- README、`docs/API.md`、`docs/DEVELOPMENT.md`。

改公共区域前要先确认不会影响对方功能包。

### 不建议互相侵入的区域

- A 不应直接重写 B 的路线推荐和景点管理页面。
- B 不应直接重写 A 的导览对话和 RAG 流程。
- 如果需要联动，优先通过接口和小组件对接。

### 推荐命名边界

- A 的后端模块可以使用：
  - `backend/app/routers/guide.py`
  - `backend/app/routers/rag.py`
  - `backend/app/routers/voice.py`
  - `backend/app/crud/guide.py`
  - `backend/app/crud/knowledge.py`
- B 的后端模块可以使用：
  - `backend/app/routers/spots.py`
  - `backend/app/routers/routes.py`
  - `backend/app/routers/admin_analytics.py`
  - `backend/app/crud/spots.py`
  - `backend/app/crud/routes.py`
- A 的前端模块可以使用：
  - `frontend/src/views/GuideView.vue`
  - `frontend/src/api/guide.ts`
  - `frontend/src/api/knowledge.ts`
  - `frontend/src/components/guide/`
- B 的前端模块可以使用：
  - `frontend/src/views/SpotListView.vue`
  - `frontend/src/views/RouteRecommendView.vue`
  - `frontend/src/views/AdminSpotView.vue`
  - `frontend/src/views/AdminAnalyticsView.vue`
  - `frontend/src/api/spots.ts`
  - `frontend/src/api/routes.ts`

## 推荐开发顺序

1. A 做知识库最小闭环和 RAG 检索，同时做游客导览页面的 mock 交互。
2. B 做景区基础数据和景点管理，同时做游客景点列表/详情。
3. A 接入真实 RAG 和模型调用，完成导览会话与回答来源展示。
4. B 完成路线推荐、路线详情和路线反馈。
5. A 完成数字人状态、TTS 播报，ASR 可作为增强项。
6. B 完成后台统计和路线/景点运营页。
7. 两人最后做联动：路线里的景点可进入 A 的数字导览讲解，A 的问答日志可进入 B 的统计页。
8. 两人共同补演示数据、SQL 初始化、README 和接口文档。

## 两人任务表

| 功能包 | 负责人 | 技术范围 | 优先级 | 第一版必须完成 |
| --- | --- | --- | --- | --- |
| 智能数字导览闭环 | A | 知识库、RAG、LLM、导览会话、游客导览页、数字人状态、TTS | P0 | RAG + 文本问答 + 来源展示 + 会话记录 |
| 语音与数字人增强 | A | ASR、TTS、数字人动效、字幕、播放控制 | P1 | TTS 播报 + 数字人状态切换 |
| 景区服务与路线闭环 | B | 景点数据、素材、路线推荐、游客路线页、反馈 | P0 | 景点 CRUD + 游客景点详情 + 路线推荐 |
| 管理后台与运营统计 | B | 管理端页面、路线反馈管理、统计接口、图表展示 | P1 | 景点管理 + 运营概览 |
| 演示稳定性与联调 | A + B | 演示数据、接口文档、错误处理、构建检查 | P0-P2 持续 | README 可复现 + 前后端可跑 |

## 每个功能包的交付清单

每个人完成自己功能时，都要同时交付：

- 数据库模型和 Alembic migration。
- 如影响协作者初始化，同步更新 `backend/sql/init_auth_schema.sql`。
- 后端 router、schema、crud/service。
- 前端 api、view、必要的 store 或 component。
- `docs/API.md` 中的接口说明。
- 最小测试或手工验收步骤。
- 不提交真实 `.env`、上传文件、缓存、构建产物。
