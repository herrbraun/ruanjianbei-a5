# 游客感受度报告与数据大屏设计

## 1. 目标与范围

本功能补齐赛题管理后台侧的两项硬性要求：

1. 分析游客交互记录，生成游客关注点、情感趋势和服务建议。
2. 展示当日/本周服务人次、热门问答、游客满意度趋势等核心运营数据。

首版复用现有 `guide_sessions`、`guide_messages`、路线反馈和游客行为数据，不引入 Redis、Celery 或新的独立服务。游客问答必须优先返回，洞察分析异步进行，分析失败不得影响导览主链路。

本设计不包含数字人语义表情、多音色扩充、RAG 排序修复、问答准确率测试和响应性能优化；这些内容作为后续独立任务处理。

## 2. 已确认决策

- 使用“异步实时分析 + 游客主动评分”。
- 使用混合分析方案：大模型输出结构化单次交互洞察，SQL 负责稳定聚合，大模型只根据聚合结果生成服务建议。
- 管理端采用方案 B：运营大屏与感受度报告中心分离。
- 分类使用固定枚举，禁止模型自由创建统计分类。
- 报告保存生成时的指标快照，历史报告不随基础数据变化。

## 3. 系统边界与数据流

```text
游客提交问题
  → 保存游客问题
  → RAG 生成并保存回答
  → 立即返回游客端
  → 创建待分析记录
  → 后台调用模型输出固定 JSON
  → 校验并保存主题、情感、意图和问题类型

游客提交评分
  → 保存或更新会话满意度
  → 大屏统计立即更新

管理员打开运营大屏
  → SQL 实时计算指标、趋势、热门问题和风险摘要

管理员生成日报/周报
  → 固化统计快照
  → 大模型仅基于快照生成服务建议
  → 保存可回看的正式报告
```

单次交互分析以游客问题为分析主体，可同时提供对应数字人回答作为上下文，以判断回答失败、未解决问题或服务风险。无论回答成功还是失败，都应创建洞察记录。

## 4. 数据模型

### 4.1 `guide_message_insights`

每个游客问题最多对应一条洞察记录。

字段：

- `id`：主键。
- `scenic_area_id`：所属景区，外键并建立日期筛选索引。
- `guide_session_id`：所属导览会话。
- `visitor_message_id`：游客问题，唯一外键。
- `assistant_message_id`：对应数字人回答，可为空。
- `normalized_question`：不超过 30 个中文字符的标准化问题。
- `primary_topic`：主要关注主题。
- `topic_tags`：多个固定主题标签，JSON 数组。
- `intent`：游客意图。
- `sentiment`：`positive`、`neutral` 或 `negative`。
- `sentiment_score`：范围 `-1.0` 到 `1.0`。
- `issue_type`：固定服务问题分类。
- `needs_attention`：是否需要管理员关注。
- `resolution_status`：`unresolved` 或 `resolved`。
- `resolved_at`、`resolved_by_user_id`：管理员处理记录。
- `analysis_status`：`pending`、`processing`、`completed` 或 `failed`。
- `analysis_model`：实际分析模型。
- `analysis_attempts`：分析尝试次数。
- `error_message`：仅管理员可见的截断错误信息。
- `analyzed_at`、`created_at`、`updated_at`。

唯一约束：`visitor_message_id`。索引至少覆盖：

- `(scenic_area_id, created_at)`；
- `(scenic_area_id, sentiment, created_at)`；
- `(analysis_status, updated_at)`；
- `(needs_attention, resolution_status, created_at)`。

### 4.2 `guide_feedbacks`

每个导览会话最多保留一份评价，重复提交为更新。

字段：

- `id`：主键。
- `guide_session_id`：唯一外键。
- `user_id`：评价游客。
- `scenic_area_id`：所属景区。
- `rating`：1 至 5 分。
- `tags`：固定评价标签 JSON 数组。
- `comment`：可选文字意见，最多 1000 字。
- `created_at`、`updated_at`。

游客至少获得一次数字人回答后才可评价，且后端必须校验会话属于当前游客。

评价标签：

- `answer_accurate`：回答准确；
- `voice_natural`：声音自然；
- `avatar_preferred`：形象喜欢；
- `slow_response`：响应较慢；
- `unresolved`：没有解决问题。

### 4.3 `scenic_insight_reports`

保存管理员生成的日报或周报。

字段：

- `id`：主键。
- `scenic_area_id`：所属景区。
- `period_type`：`daily` 或 `weekly`。
- `period_start`、`period_end`：报告周期。
- `metrics_snapshot`：生成时的完整聚合指标 JSON。
- `summary`：本期概述。
- `attention_points`：主要关注点 JSON。
- `risk_findings`：风险问题 JSON。
- `recommendations`：3 至 5 条可执行建议 JSON。
- `generation_status`：`pending`、`processing`、`completed` 或 `failed`。
- `generation_model`、`error_message`。
- `created_by_user_id`、`generated_at`、`created_at`。

同一景区、报告类型、起止日期允许重新生成并保留历史版本，不做覆盖。

## 5. 固定分析口径

### 5.1 关注主题

- 历史文化
- 景点特色
- 演出活动
- 开放时间
- 游览路线
- 交通停车
- 门票价格
- 餐饮购物
- 公共设施
- 无障碍与特殊需求
- 服务体验
- 其他

### 5.2 游客意图

- 知识咨询
- 路线推荐
- 服务咨询
- 投诉反馈
- 闲聊互动
- 其他

### 5.3 情感

- 正面：`positive`
- 中性：`neutral`
- 负面：`negative`

### 5.4 服务问题

- 排队时间
- 路线指引
- 价格问题
- 环境卫生
- 工作人员服务
- 数字人回答不准确
- 响应速度
- 语音或数字人体验
- 设施问题
- 无明确问题

模型输出必须经过 Pydantic 结构校验。`topic_tags` 去重且只能来自固定主题；`primary_topic` 必须包含在 `topic_tags` 中；`normalized_question` 必须去除游客身份信息且不超过 30 个中文字符。

## 6. 异步分析与恢复

游客回答保存后：

1. 在同一数据库事务或紧随其后的幂等操作中创建 `pending` 洞察记录。
2. 使用 FastAPI 后台任务启动分析，不延长游客接口响应。
3. 任务开始时原子地把状态改为 `processing` 并增加 `analysis_attempts`。
4. 调用配置的大模型，要求返回固定 JSON。
5. JSON 格式错误时允许一次格式修复请求。
6. 校验成功后写入分类结果并标记 `completed`。
7. 网络、模型或校验错误时标记 `failed`，保存最多 2000 字的内部错误。

管理员可单条重试或批量重试失败记录。应用启动时将超过 10 分钟仍处于 `processing` 的记录恢复为 `pending`，防止服务异常退出后任务永久卡住。恢复操作必须幂等，不重复创建洞察记录。

基础指标不依赖分析完成状态；情感、主题和热门问题仅统计 `completed` 数据，并在大屏显示“洞察分析覆盖率”。

## 7. 运营大屏

路由：`/admin/analytics`。

顶部筛选：

- 必选景区；
- 今日、本周、近 30 天、自定义日期；
- 与上一等长周期比较；
- 手动刷新；
- 生成日报/周报入口。

指标卡：

- 服务游客数：周期内产生导览会话的去重 `user_id` 数量；
- 导览会话数；
- 游客提问数：游客角色消息数量；
- 回答成功率：成功回答数除以全部回答数；
- 平均回答耗时：成功回答的 `answer_duration_ms` 平均值；
- 平均满意度：`guide_feedbacks.rating` 平均值；
- 负面情感占比：负面洞察数除以已完成洞察数；
- 洞察分析覆盖率：已完成洞察数除以应分析游客问题数。

图表与列表：

- 每日服务游客、会话和问题数量趋势；
- 每日正面、中性、负面情感趋势；
- 每日满意度趋势；
- 游客关注点分布；
- 热门标准化问题排行；
- 未处理风险问题预览。

现有路线生成、热门兴趣、热门景点和游客行为统计保留在下方“路线与景点运营”区域。

所有日期边界按 `Asia/Shanghai` 解释，结束日期包含当天。无评价时满意度显示“暂无”，不得显示为 0 分。

## 8. 感受度报告中心

路由：`/admin/insights`。

页面包含两个标签：

1. 感受度报告：日报、周报列表和报告详情。
2. 风险问题：筛选、查看、重试分析和标记处理。

报告详情：

- 服务规模摘要；
- 热门关注点；
- 情感变化；
- 热门问题及出现次数；
- 满意度和低分标签；
- 未处理风险问题摘要；
- AI 服务改进建议；
- 分析模型和生成时间。

风险问题支持按景区、日期、情感、问题类型、分析状态和处理状态筛选。默认只显示脱敏问题摘要，展开后才显示完整问答。

## 9. 游客评价交互

游客获得至少一次数字人回答后，在对话区域底部显示非强制评价入口：

- 1 至 5 分；
- 多选固定评价标签；
- 可选文字意见；
- 提交后允许更新。

移动端不得用弹窗阻断导览，不得覆盖文本输入、录音按钮或数字人舞台。评价提交失败保留用户当前输入并提供重试。

## 10. API 设计

### 10.1 游客接口

```text
POST /api/guide/sessions/{session_id}/feedback
GET  /api/guide/sessions/{session_id}/feedback
```

`POST` 请求：

```json
{
  "rating": 5,
  "tags": ["answer_accurate", "voice_natural"],
  "comment": "讲解清楚，语速合适"
}
```

### 10.2 管理端运营大屏

```text
GET /api/admin/analytics/guide
    ?scenic_area_id=1
    &start_date=2026-07-01
    &end_date=2026-07-07
```

单次返回指标卡、上一周期对比、服务趋势、情感趋势、满意度趋势、关注点、热门问题和风险摘要，避免前端为一张大屏发起大量并行请求。

### 10.3 管理端洞察与报告

```text
GET   /api/admin/insights/messages
POST  /api/admin/insights/messages/{insight_id}/retry
POST  /api/admin/insights/messages/retry-failed
PATCH /api/admin/insights/messages/{insight_id}/resolve

POST /api/admin/insight-reports
GET  /api/admin/insight-reports
GET  /api/admin/insight-reports/{report_id}
```

消息列表必须分页，默认每页 20 条，最大 100 条。所有接口要求管理员身份，并强制按所选景区和日期范围查询。

## 11. 报告生成

报告的统计数字全部由 SQL 计算。发送给报告模型的内容只包含脱敏聚合结果：

```json
{
  "service_visitors": 286,
  "session_count": 312,
  "question_count": 612,
  "answer_success_rate": 0.96,
  "average_rating": 4.7,
  "negative_rate": 0.082,
  "analysis_coverage_rate": 0.98,
  "top_topics": [],
  "popular_questions": [],
  "issue_distribution": []
}
```

模型只生成：

- 本期概述；
- 三个主要关注点；
- 情感变化解释；
- 风险问题；
- 三至五条可执行服务建议。

模型不能修改统计数字。生成失败时保留指标快照并允许重试，不生成虚假建议。

## 12. 权限与隐私

- 游客只能读取和更新自己的会话评价。
- 运营大屏、洞察消息和报告接口仅管理员访问。
- 报告模型输入不包含用户名、头像、IP、手机号或完整游客身份。
- 风险问题默认只展示问题摘要；完整问答需要管理员主动展开。
- 游客响应不得包含模型错误、数据库异常、文件路径或提示词。
- 导出或展示报告不得包含 JWT、供应商错误详情和内部知识库路径。

## 13. 错误与空状态

- 分析失败：主导览不受影响，大屏覆盖率下降，风险列表显示可重试状态。
- 报告生成失败：保留统计快照，显示失败原因摘要和重新生成按钮。
- 无评价：显示“暂无评价”，不把空值计入平均分。
- 无分析数据：基础服务指标仍显示，主题和情感区域说明“洞察分析处理中”。
- 部分分析失败：图表只统计成功记录，并明确显示覆盖率和失败数量。
- 日期或景区无数据：展示空状态，不沿用上一次查询结果。

## 14. 验收标准

### 14.1 后端

- 每个游客问题最多产生一条洞察记录。
- 创建洞察记录和后台分析不增加游客问答接口的模型等待阶段。
- 非法模型 JSON 被拒绝或经一次格式修复后通过。
- 分析失败可单条和批量重试。
- 超时 `processing` 记录可在启动恢复后重新处理。
- 不同景区的大屏、洞察、评价和报告严格隔离。
- 今日、本周、近 30 天和自定义日期统计按上海时区正确计算。
- 服务游客、会话、问题数、成功率、情感比例、覆盖率和满意度计算正确。
- 游客不能读取或修改其他会话的评价。
- 普通游客无法访问管理端洞察和报告接口。

### 14.2 前端

- 景区、日期和上一周期筛选生效。
- 大屏同时覆盖服务量、热门问答、情感趋势和满意度趋势。
- 空数据、部分失败、加载失败和报告生成失败都有明确状态。
- 报告生成中、成功、失败和重新生成状态清晰。
- 风险问题可筛选、查看、重试和标记处理。
- 游客评价在常见手机宽度下不遮挡对话、录音按钮和数字人。
- 现有路线、景点、知识库和数字人功能不回归。

### 14.3 验证命令

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m pytest -q -p no:cacheprovider

cd ..\frontend
npm.cmd run build
```

另需使用真实模型执行一次洞察分析和一次报告生成冒烟测试，确认模型返回可以通过结构校验，但自动化测试不得消耗真实模型额度。
