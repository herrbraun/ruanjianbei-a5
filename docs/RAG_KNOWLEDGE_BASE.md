# 多景区 RAG 知识库

本说明取代 `DEVELOPMENT.md` 中“第一阶段暂不实现 RAG”的历史边界说明。

运行时数据库使用 Docker pgvector（由 `scripts/start-pgvector.ps1` 选择的 `localhost:5433`）。原生 PostgreSQL 的 5432 不作为应用运行时数据库。

管理员在 `/admin/knowledge` 按三层配置：

1. 创建或选择景区。
2. 创建草稿 RAG Profile，并绑定一份或多份可复用知识库。
3. 上传资料到指定知识库；验证检索结果后，将 Profile 切换为正式版。

上传后管理端每 1 秒刷新一次资料状态。后端在解析完成后写入 `chunk_count`，并在每批最多 10 段 embedding 完成后更新 `embedding_count`，页面会据此展示处理进度；所有资料进入 `indexed` 或 `failed` 后自动停止轮询。

同一景区最多只能有一个 `active` Profile。切换时旧正式 Profile 自动归档。游客调用 `/api/rag/search` 时只提供 `scenic_area_code`，服务端会自动解析该景区的正式 Profile 和已绑定知识库。

资料上传限制为 20 MB，支持 DOCX、TXT 和可提取文字的 PDF。扫描型 PDF 会标记失败并提示先 OCR；Excel 不进入 RAG。原文件保存在已忽略的 `backend/uploads/knowledge/`，向量使用 DashScope 原生 `text-embedding-v4`、1024 维，文档和查询分别使用 `document`、`query` 的 `text_type`。

首版使用 pgvector 余弦精确检索和普通筛选索引。有效 chunk 数量达到约 1 万后，再通过单独迁移评估并创建 HNSW 索引。

首个初始化景区为 `lingshan`（灵山胜境），其“灵山结构化景点资料库”优先级为 100，“灵山历史文化资料库”优先级为 10，并由“灵山正式版 RAG”共同绑定。

管理员检索预览会先执行真实向量召回，再调用 `LLM_CHAT_MODEL`（默认 `qwen-plus`）生成一份仅基于命中片段的示例回答。回答中的 `[资料1]`、`[资料2]` 与下方检索片段编号对应；模型调用失败时仍保留检索结果，并单独展示失败原因。

已完成或失败的资料可在管理端删除。删除会级联移除 `knowledge_documents`、`knowledge_chunks` 和 `knowledge_embeddings` 中的记录，并清理已忽略目录中的原文件；处于 `pending` 或 `indexing` 的任务为避免并发冲突，不允许删除。
