# Visitor Insights and Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add asynchronous visitor sentiment/topic analysis, guide-session feedback, a scenic-area guide operations dashboard, and persistent daily/weekly visitor insight reports.

**Architecture:** Keep the existing Vue + FastAPI + SQLAlchemy layering. Persist one insight per visitor question, run a structured DashScope analysis after the guide response is committed, calculate dashboard metrics deterministically with SQL, and let the LLM generate prose recommendations only from a persisted aggregate snapshot. Add `/admin/insights` as a separate report/risk workspace while extending the existing `/admin/analytics` page.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL/SQLite tests, Pydantic 2, httpx, Vue 3, TypeScript, Element Plus, ECharts.

## Global Constraints

- Visitor chat response must not wait for insight analysis.
- One `guide_message_insights` row per visitor message; all creation and retry paths must be idempotent.
- Topic, intent, sentiment, issue and feedback labels are closed enums defined in the approved design.
- Dashboard statistics use `Asia/Shanghai` date boundaries and an inclusive end date.
- LLM report generation receives aggregate/de-identified data only and cannot invent or modify metrics.
- No Redis, Celery, new service, or new frontend state library.
- All admin analytics, insight and report endpoints require `require_admin`.
- SQLite automated tests must not call real model APIs; one manual real-model smoke test is required after automated verification.
- Existing route, spot, knowledge, avatar, guide, ASR and TTS behavior must remain compatible.

---

### Task 1: Persist insights, feedback, and reports

**Files:**
- Modify: `backend/app/models/guide.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/202607160002_add_visitor_insights.py`
- Modify: `backend/sql/init_auth_schema.sql`
- Modify: `backend/app/schemas/guide.py`
- Create: `backend/app/schemas/insights.py`
- Test: `backend/tests/test_guide_feedback.py`

**Interfaces:**
- Produces models `GuideMessageInsight`, `GuideFeedback`, `ScenicInsightReport`.
- Produces `GuideFeedbackUpsert`, `GuideFeedbackOut`, fixed `FeedbackTag` validation.
- Produces insight/report response schemas consumed by Tasks 2–6.

- [ ] **Step 1: Write failing model and feedback validation tests**

Create tests that build metadata in SQLite and assert feedback tags reject values outside:

```python
{"answer_accurate", "voice_natural", "avatar_preferred", "slow_response", "unresolved"}
```

Also assert `GuideMessageInsight.visitor_message_id` and `GuideFeedback.guide_session_id` are unique.

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m pytest tests/test_guide_feedback.py -q -p no:cacheprovider
```

Expected: collection/import failure because the new schemas and models do not exist.

- [ ] **Step 3: Add models, relationships, constraints, schemas, and migration**

Implement:

```python
class GuideMessageInsight(Base):
    visitor_message_id: Mapped[int] = mapped_column(
        ForeignKey("guide_messages.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    analysis_status: Mapped[str] = mapped_column(String(20), default="pending")
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

class GuideFeedback(Base):
    guide_session_id: Mapped[int] = mapped_column(
        ForeignKey("guide_sessions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

class ScenicInsightReport(Base):
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    generation_status: Mapped[str] = mapped_column(String(20), default="pending")
```

Add database check constraints for all fixed states, rating 1–5 and sentiment score -1 to 1. Add the approved composite indexes and foreign-key relationships. The migration revision is `202607160002` with `down_revision = "202607160001"`; its downgrade drops the three tables in reverse dependency order. Mirror the same tables in `backend/sql/init_auth_schema.sql`.

- [ ] **Step 4: Run model/schema tests**

Expected: focused tests pass and `python -m alembic heads` prints only `202607160002 (head)`.

- [ ] **Step 5: Commit Task 1**

```powershell
git add backend/app/models backend/app/schemas backend/alembic/versions/202607160002_add_visitor_insights.py backend/sql/init_auth_schema.sql backend/tests/test_guide_feedback.py
git commit -m "feat: add visitor insight data model"
```

### Task 2: Add visitor guide feedback API

**Files:**
- Modify: `backend/app/crud/guide.py`
- Modify: `backend/app/routers/guide.py`
- Modify: `backend/tests/test_guide_feedback.py`

**Interfaces:**
- Produces `get_guide_feedback(db, session_id)` and `upsert_guide_feedback(db, session, user_id, payload)`.
- Produces `GET/POST /api/guide/sessions/{session_id}/feedback`.

- [ ] **Step 1: Add failing endpoint tests**

Test these cases using seeded scenic area/profile and messages:

```python
assert post_before_answer.status_code == 422
assert create_feedback.status_code == 200
assert create_feedback.json()["rating"] == 5
assert update_feedback.json()["rating"] == 3
assert other_visitor_get.status_code == 404
assert admin_post.status_code == 403
```

- [ ] **Step 2: Run focused tests and verify endpoint 404 failures**

- [ ] **Step 3: Implement feedback CRUD and routes**

The POST route must call `_session_or_404`, verify at least one assistant message exists, strip the optional comment, and upsert the row keyed by `guide_session_id`. The GET route returns `204` when the current visitor has not submitted feedback and `200` otherwise. Both routes use `require_visitor`.

- [ ] **Step 4: Run feedback tests and the existing guide tests**

```powershell
python -m pytest tests/test_guide_feedback.py tests/test_guide_routes.py -q -p no:cacheprovider
```

- [ ] **Step 5: Commit Task 2**

```powershell
git add backend/app/crud/guide.py backend/app/routers/guide.py backend/tests/test_guide_feedback.py
git commit -m "feat: collect guide session feedback"
```

### Task 3: Analyze guide interactions asynchronously

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Create: `backend/app/services/interaction_insight.py`
- Create: `backend/app/crud/insights.py`
- Modify: `backend/app/routers/guide.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_interaction_insight.py`
- Modify: `backend/tests/test_guide_routes.py`

**Interfaces:**
- Produces Pydantic model `InteractionInsightResult`.
- Produces `analyze_interaction(question, answer, answer_status, client=None) -> InteractionInsightResult`.
- Produces `ensure_pending_insight(...)`, `process_insight(insight_id)`, `recover_stale_insights(db, stale_before)`.

- [ ] **Step 1: Write failing structured-analysis tests**

Use `httpx.MockTransport` to verify the configured model receives only question, answer, status and the fixed taxonomy. Assert a fenced JSON response is parsed into:

```python
InteractionInsightResult(
    normalized_question="九龙灌浴演出时间",
    primary_topic="演出活动",
    topic_tags=["演出活动", "开放时间"],
    intent="服务咨询",
    sentiment="neutral",
    sentiment_score=0.0,
    issue_type="无明确问题",
    needs_attention=False,
)
```

Assert invalid labels fail validation and one repair request is attempted. Test stale `processing` rows become `pending` and duplicate `ensure_pending_insight` calls return the same row.

- [ ] **Step 2: Run tests and verify import failures**

- [ ] **Step 3: Implement structured model analysis**

Add `INSIGHT_ANALYSIS_MODEL` defaulting to `qwen-plus`. Request JSON output from the existing compatible chat endpoint with temperature `0.1`, a 60-second timeout and no visitor identity. Strip Markdown fences, validate with Pydantic, and make one repair call when JSON/schema validation fails.

- [ ] **Step 4: Implement idempotent persistence and hook chat**

Change the chat route to accept `BackgroundTasks`. After both visitor and assistant messages exist, call `ensure_pending_insight` and schedule `process_insight` with only the database row ID. `process_insight` opens its own `SessionLocal`, atomically marks the row `processing`, calls the service, and writes completed fields; failures write `failed` and a 2000-character error.

On FastAPI startup/lifespan, reset insights left `processing` for over 10 minutes back to `pending`. Do not call external models during startup.

- [ ] **Step 5: Run tests proving chat returns before analysis executes**

Override/spy on `BackgroundTasks` work and assert the chat response is produced with a pending insight even when the analyzer later fails.

- [ ] **Step 6: Commit Task 3**

```powershell
git add backend/app/config.py backend/.env.example backend/app/services/interaction_insight.py backend/app/crud/insights.py backend/app/routers/guide.py backend/app/main.py backend/tests
git commit -m "feat: analyze visitor interactions asynchronously"
```

### Task 4: Build deterministic guide dashboard analytics

**Files:**
- Modify: `backend/app/crud/insights.py`
- Modify: `backend/app/schemas/insights.py`
- Modify: `backend/app/routers/admin_analytics.py`
- Create: `backend/tests/test_guide_analytics.py`

**Interfaces:**
- Produces `get_guide_dashboard(db, scenic_area_id, start_date, end_date) -> dict`.
- Produces `GET /api/admin/analytics/guide`.

- [ ] **Step 1: Write failing aggregation and authorization tests**

Seed two scenic areas with sessions, user/assistant messages, completed/failed insights and feedback. Assert:

```python
assert metrics["service_visitors"] == 2
assert metrics["session_count"] == 3
assert metrics["question_count"] == 5
assert metrics["answer_success_rate"] == 0.8
assert metrics["analysis_coverage_rate"] == 0.8
assert metrics["average_rating"] == 4.5
```

Also assert no second-scenic data leaks, empty averages are `None`, end date is inclusive, and a visitor receives 403.

- [ ] **Step 2: Run tests and verify missing endpoint**

- [ ] **Step 3: Implement Shanghai date boundaries and SQL aggregation**

Convert local start at `00:00:00 Asia/Shanghai` and local day after end at `00:00:00` to UTC, then use a half-open `[start, end)` query. Return:

```python
{
  "period": {...},
  "metrics": {...},
  "previous_period": {...},
  "service_trend": [...],
  "sentiment_trend": [...],
  "satisfaction_trend": [...],
  "topic_distribution": [...],
  "popular_questions": [...],
  "attention_preview": [...],
}
```

Use SQL group/count/avg operations, not Python loading of all messages. Limit popular questions to 10 and attention preview to 8.

- [ ] **Step 4: Add admin endpoint and run tests**

Validate the scenic area exists and `start_date <= end_date <= start_date + 365 days`.

- [ ] **Step 5: Commit Task 4**

```powershell
git add backend/app/crud/insights.py backend/app/schemas/insights.py backend/app/routers/admin_analytics.py backend/tests/test_guide_analytics.py
git commit -m "feat: add guide operations analytics"
```

### Task 5: Add risk workflow and persistent reports

**Files:**
- Create: `backend/app/services/insight_report.py`
- Create: `backend/app/routers/insights.py`
- Modify: `backend/app/crud/insights.py`
- Modify: `backend/app/schemas/insights.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_insight_reports.py`

**Interfaces:**
- Produces paginated insight list, retry, bulk retry and resolve endpoints.
- Produces `generate_insight_report(snapshot, client=None) -> ReportNarrative`.
- Produces report create/list/detail endpoints.

- [ ] **Step 1: Write failing admin workflow tests**

Assert filters by scenic area, sentiment, issue, analysis state and resolution state; page size over 100 fails; retry only changes `failed` to `pending`; resolve records current admin and timestamp; visitors receive 403.

Test report generation with an `httpx.MockTransport` and assert the request includes aggregate snapshot but excludes question content, usernames and IP addresses. Assert metrics in the stored snapshot exactly equal dashboard metrics.

- [ ] **Step 2: Run tests and verify missing routes/services**

- [ ] **Step 3: Implement insight admin routes**

Use `GET /api/admin/insights/messages`, `POST /retry`, `POST /retry-failed`, and `PATCH /resolve`. Return stable pagination metadata. Schedule retried analysis through `BackgroundTasks` without waiting.

- [ ] **Step 4: Implement report generation and persistence**

Create the report row and snapshot first, then schedule generation. The model returns strict JSON with `summary`, three `attention_points`, `risk_findings`, and 3–5 `recommendations`. Failure preserves `metrics_snapshot`, sets `failed`, and supports creating a new report version.

- [ ] **Step 5: Register router, run tests, and commit**

```powershell
git add backend/app/services/insight_report.py backend/app/routers/insights.py backend/app/crud/insights.py backend/app/schemas/insights.py backend/app/main.py backend/tests/test_insight_reports.py
git commit -m "feat: add visitor insight reports"
```

### Task 6: Add visitor feedback and admin insight UI

**Files:**
- Modify: `frontend/src/api/guide.ts`
- Modify: `frontend/src/api/analytics.ts`
- Create: `frontend/src/api/insights.ts`
- Modify: `frontend/src/views/VisitorView.vue`
- Modify: `frontend/src/views/AdminAnalyticsView.vue`
- Create: `frontend/src/views/AdminInsightsView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/AppLayout.vue`
- Modify: `frontend/src/a-features.css`

**Interfaces:**
- Adds typed feedback, dashboard, insight list and report API clients.
- Adds `/admin/insights` route and sidebar navigation.

- [ ] **Step 1: Add TypeScript API contracts**

Define exact response interfaces matching backend schemas. All dates remain ISO strings; percentages remain decimal values from 0 to 1. Use the standard 10-second timeout for dashboard/list CRUD and `AI_API_TIMEOUT_MS` for report generation/retry calls that schedule model work.

- [ ] **Step 2: Implement mobile guide feedback card**

After at least one assistant response, show a collapsible non-modal card with `el-rate`, five checkbox tags, optional 1000-character comment and submit/update button. Load existing feedback when session changes. Preserve form state on request failure.

- [ ] **Step 3: Extend the operations dashboard**

Add scenic/date controls, eight metrics, service/sentiment/satisfaction charts, topic distribution, popular questions and attention preview above existing route/spot sections. Render `None` averages as “暂无” and show analysis coverage/failure counts.

- [ ] **Step 4: Implement `/admin/insights`**

Add report and risk tabs. Report tab supports list, period filters, generation and detail. Risk tab supports server pagination and filters, expanded de-identified dialogue, retry and resolve. All async states have loading, empty and error UI.

- [ ] **Step 5: Run frontend build and manually inspect mobile/desktop layouts**

```powershell
cd frontend
npm.cmd run build
```

Expected: TypeScript and Vite succeed; only existing chunk-size warnings are acceptable.

- [ ] **Step 6: Commit Task 6**

```powershell
git add frontend/src
git commit -m "feat: add visitor insight dashboard UI"
```

### Task 7: Migrate, verify, and document

**Files:**
- Modify: `README.md`
- Modify: `docs/API.md`
- Modify: `docs/DEVELOPMENT.md`

**Interfaces:**
- Documents runtime model setting, migration, dashboard definitions, report flow, and manual smoke test.

- [ ] **Step 1: Run all automated verification**

```powershell
cd backend
$env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages')
python -m pytest -q -p no:cacheprovider
python -m alembic heads
python -m alembic upgrade head
python -m alembic current

cd ..\frontend
npm.cmd run build
```

Expected: all tests pass, one Alembic head/current at `202607160002`, frontend build succeeds.

- [ ] **Step 2: Run real-model smoke tests**

Create one pending insight against an existing real guide exchange and run `process_insight(id)`. Confirm it becomes `completed` with fixed labels. Generate one report from the current scenic area and confirm strict narrative JSON persists. Do not print API keys or full visitor identity.

- [ ] **Step 3: Run HTTP permission and data checks**

Verify visitor feedback create/update, visitor rejection from admin endpoints, scenic filtering, empty period behavior, risk retry/resolve, report list/detail, and no internal error in visitor responses.

- [ ] **Step 4: Update documentation**

Document `INSIGHT_ANALYSIS_MODEL`, migration command, endpoint summary, metric definitions, retry behavior and the report privacy boundary. Remove the stale statement that RAG/digital-human/analytics features are unimplemented.

- [ ] **Step 5: Final commit**

```powershell
git add README.md docs/API.md docs/DEVELOPMENT.md
git commit -m "docs: document visitor insight operations"
```

- [ ] **Step 6: Review final diff and status**

Run `git status --short --ignored`, `git diff HEAD~7 --check`, and inspect that `.env`, uploaded knowledge files, generated reports, `.superpowers`, build output and caches are not tracked.
