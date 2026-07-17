# API 约定

## 数字人管理与游客端

所有 `/admin/avatars/*` 接口要求管理员 Bearer Token：

- `GET /admin/avatars/voices`：读取允许配置的系统音色。
- `GET|POST /admin/avatars/humans`、`PATCH|DELETE /admin/avatars/humans/{id}`：管理人物中文名、定位、音色、讲解风格与启停状态。
- `GET /admin/avatars/scenic-configs?scenic_area_id={id}`：读取景区上架版本。
- `POST /admin/avatars/variants`：以 `multipart/form-data` 上传 `.vrm`，包含人物、景区、服装、版本、缩略图、上架/默认/排序与文件字段。文件最大 80MB，服务端校验 GLB 文件头并随机命名存储。
- `PATCH|DELETE /admin/avatars/variants/{id}`、`PATCH /admin/avatars/scenic-configs/{id}`：编辑外观资料、删除外观或控制当前景区的上架、默认与排序。

游客端接口要求游客 JWT：

- `GET /avatars/scenic-areas/{scenic_area_code}`：只返回当前景区已上架、已启用人物的外观列表及默认版本。
- `GET /avatars/scenic-areas/{scenic_area_code}/variants/{id}/asset`：仅提供当前景区已上架版本的 VRM 二进制文件。
- `POST /guide/messages/{message_id}/speech?avatar_variant_id={id}`：若传入版本 ID，后端先验证其已在当前会话景区上架，再使用该人物配置的系统音色与讲解风格；未传时回退到景区默认数字人，保持旧调用兼容。

后端默认地址：`http://localhost:8000/api`

## 游客注册与登录

`POST /auth/visitor-register`

首次注册提交账号和密码，成功后直接返回 JWT 和用户信息；账号占用时返回 `409`，`detail.suggestions` 提供三个可选账号。

```json
{
  "username": "visitor001",
  "password": "password123"
}
```

`POST /auth/visitor-login`

请求：

```json
{
  "username": "visitor001",
  "password": "password123"
}
```

返回：

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "user": {
    "id": 2,
    "role": "visitor",
    "nickname": "visitor001",
    "username": "visitor001",
    "avatar_url": null,
    "interest": null,
    "interests": [],
    "needs_interest_setup": true
  }
}
```

## 管理员登录

`POST /auth/admin-login`

请求：

```json
{
  "username": "admin",
  "password": "your-admin-password"
}
```

返回：

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "role": "admin",
    "nickname": "系统管理员",
    "username": "admin",
    "interest": null
  }
}
```

## 当前用户

`GET /auth/me`

请求头：

```http
Authorization: Bearer <jwt-token>
```

返回当前登录用户信息。

账号相关接口：

- `GET /auth/username-availability?username={账号}`：检查账号并返回可选账号。
- `GET /auth/interests`：读取可选兴趣标签。
- `PATCH /auth/me`：修改昵称和兴趣标签。
- `POST /auth/change-password`：验证原密码并修改密码。
- `POST /auth/avatar`：上传 PNG、JPEG 或 WebP 头像，最大 5 MB。

## 景点与路线

游客接口均要求游客 Bearer Token：

- `GET /spots`、`GET /spots/{id}`：查询启用景点及详情。
- `POST /routes/recommend`：按兴趣、时长、起点和偏好生成并保存路线。
- `GET /routes/{id}`：读取当前游客自己的路线。
- `POST /routes/{id}/feedback`：提交 1 至 5 分评价和反馈内容。

管理接口均要求管理员 Bearer Token：

- `GET|POST /admin/spots`、`PUT /admin/spots/{id}`：查询、新增和编辑景点。
- `PATCH /admin/spots/{id}/status`：启用或停用景点。
- `/admin/spots/{id}/media`：维护景点图片、视频和音频。
- `/admin/routes/settings`、`GET /admin/routes`：维护推荐设置并查看路线记录。
- `GET /admin/analytics/overview`：读取登录、景点、路线、反馈和游客行为统计。

## RAG 知识库管理

以下 `/admin/*` 接口均要求管理员 Bearer Token：

- `GET/POST /admin/scenic-areas`
- `GET/POST /admin/knowledge-bases`
- `GET/POST /admin/rag-profiles`
- `POST /admin/rag-profiles/{id}/activate`
- `POST /admin/knowledge/documents`：上传 DOCX、TXT 或文本型 PDF。
- `GET /admin/knowledge/documents?knowledge_base_id={id}`：读取资料及实时索引计数。
- `POST /admin/knowledge/documents/{id}/index`：重新索引。
- `DELETE /admin/knowledge/documents/{id}`：级联删除资料、切片和向量；索引中的任务返回 `409`。
- `GET /admin/knowledge/documents/{id}/chunks`

`POST /admin/rag/search-preview` 会执行向量检索并真实调用聊天模型。除检索结果外，响应包含：

```json
{
  "ai_answer": "根据资料生成的回答。[资料1]",
  "answer_model": "qwen-plus",
  "answer_duration_ms": 2085,
  "answer_status": "success",
  "answer_error": null
}
```

模型生成失败不会丢失本次检索结果，此时 `answer_status` 为 `failed`，错误说明写入 `answer_error`。

游客使用：

- `GET /scenic-areas`
- `POST /rag/search`：只接收景区编码、问题和可选 `top_k`，后端自动使用该景区当前正式 Profile。
# 游客导览会话

- `POST /api/guide/sessions`：游客为一个景区创建导览会话，提交 `{ "scenic_area_code": "lingshan" }`；也可同时传入 `route_plan_id` 与 `current_spot_id`，从个性化路线的指定站点开始。
- `GET /api/guide/sessions`：获取当前游客的会话。
- `GET /api/guide/sessions/{session_id}`：读取当前游客自己的完整会话及已绑定路线、当前景点。
- `GET|PATCH /api/guide/sessions/{session_id}/context`：读取或更新路线导览进度；后端校验路线归属、景区匹配及景点确实属于路线。
- `GET /api/guide/sessions/{session_id}/messages`：获取当前游客自己的会话消息。
- `POST /api/guide/sessions/{session_id}/messages`：提交 `{ "content": "灵山大佛有什么文化意义？", "input_mode": "text" }`，返回游客问题、带资料引用的 AI 回答和实际 RAG Profile；已绑定路线时，检索与回答自动携带当前景点、完整行程及游客兴趣。
- `POST /api/guide/asr`：以 `multipart/form-data` 上传短录音字段 `file`，返回识别后的文本；录音会临时转为 16 kHz WAV 并在请求结束后删除。
- `POST /api/guide/messages/{message_id}/speech`：为当前游客自己的 AI 回答生成并返回音频流。

导览接口仅对游客 JWT 开放。每次提问均解析所选景区当时的正式 RAG Profile，并在回答记录中保存 Profile 与来源快照。

## 游客评价与感受度分析

游客接口：

- `GET /api/guide/sessions/{session_id}/feedback`：读取当前游客自己的会话评价；未评价时返回 `204`。
- `POST /api/guide/sessions/{session_id}/feedback`：新增或更新评价，请求包含 `rating`（1–5）、`tags` 和可选 `comment`。

可用标签为 `answer_accurate`、`voice_natural`、`avatar_preferred`、`slow_response`、`unresolved`。内部模型错误不会通过游客消息接口返回。

管理员接口：

- `GET /api/admin/analytics/guide?scenic_area_id={id}&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`：读取指定景区的核心指标、上期对比、服务/情绪/满意度趋势、主题、热门问题和待关注预览。
- `GET /api/admin/insights/messages`：按景区、情绪、问题类型、分析状态、关注状态和解决状态分页筛选互动洞察。
- `POST /api/admin/insights/messages/{id}/retry`、`POST /api/admin/insights/messages/retry-failed`：重试单条或批量失败分析。
- `PATCH /api/admin/insights/messages/{id}/resolve`：标记事项已解决或重新打开。
- `POST /api/admin/insight-reports`：按景区、日报/周报和日期范围创建异步报告。
- `GET /api/admin/insight-reports`、`GET /api/admin/insight-reports/{id}`：查询报告列表和生成结果。

互动分析和报告均使用独立模型配置。互动分析失败不会影响游客问答；应用启动时会把异常中断的处理中任务恢复到待处理状态。
