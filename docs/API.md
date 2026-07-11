# API 约定

后端默认地址：`http://localhost:8000/api`

## 游客登录

`POST /auth/visitor-login`

请求：

```json
{
  "nickname": "游客001",
  "interest": "历史文化"
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
    "nickname": "游客001",
    "username": null,
    "interest": "历史文化"
  }
}
```

## 管理员登录

`POST /auth/admin-login`

请求：

```json
{
  "username": "admin",
  "password": "123456"
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

- `POST /api/guide/sessions`：游客为一个景区创建导览会话，提交 `{ "scenic_area_code": "lingshan" }`。
- `GET /api/guide/sessions`：获取当前游客的会话。
- `GET /api/guide/sessions/{session_id}/messages`：获取当前游客自己的会话消息。
- `POST /api/guide/sessions/{session_id}/messages`：提交 `{ "content": "灵山大佛有什么文化意义？", "input_mode": "text" }`，返回游客问题、带资料引用的 AI 回答和实际 RAG Profile。
- `POST /api/guide/asr`：以 `multipart/form-data` 上传短录音字段 `file`，返回识别后的文本；录音会临时转为 16 kHz WAV 并在请求结束后删除。
- `POST /api/guide/messages/{message_id}/speech`：为当前游客自己的 AI 回答生成并返回音频流。

导览接口仅对游客 JWT 开放。每次提问均解析所选景区当时的正式 RAG Profile，并在回答记录中保存 Profile 与来源快照。
