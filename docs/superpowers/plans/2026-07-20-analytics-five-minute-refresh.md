# 运营大屏五分钟自动刷新 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理端运营大屏在页面可见时每 5 分钟自动刷新，并展示最近一次成功更新时间。

**Architecture:** 在独立工具中定义刷新间隔和到期判断，由 `AdminAnalyticsView.vue` 负责定时器、Page Visibility API、加载并发保护和生命周期清理。现有后端接口与统计口径不变。

**Tech Stack:** Vue 3、TypeScript、Node.js 内置测试运行器、Vite。

## Global Constraints

- 自动刷新间隔固定为 300000 毫秒。
- 页面不可见时不得发起自动刷新请求。
- 不新增 npm 依赖，不修改后端。
- 最近更新时间只在所有统计请求成功后更新。

---

### Task 1: 到期判断与运营大屏接入

**Files:**
- Create: `frontend/src/utils/periodicRefresh.ts`
- Create: `frontend/tests/periodicRefresh.test.ts`
- Modify: `frontend/src/views/AdminAnalyticsView.vue`
- Modify: `frontend/package.json`

**Interfaces:**
- Produces: `AUTO_REFRESH_INTERVAL_MS = 300000`
- Produces: `isPeriodicRefreshDue(lastSuccessfulRefresh: number | undefined, now: number): boolean`
- Consumes: existing `loadAnalytics()` and Vue mount/unmount lifecycle.

- [x] **Step 1: Write the failing test**

  Add Node tests asserting that an undefined timestamp is due, 299999 milliseconds is not due, and 300000 milliseconds is due.

- [x] **Step 2: Run test to verify it fails**

  Run `node --test --experimental-strip-types frontend/tests/periodicRefresh.test.ts` and expect module resolution to fail because `periodicRefresh.ts` does not exist.

- [x] **Step 3: Write minimal implementation**

  Add the interval constant and pure boundary helper, then update `AdminAnalyticsView.vue` to start a visibility-aware timer after initialization, skip overlapping loads, refresh stale data when the tab becomes visible, record successful refresh time, and clean up on unmount. Add a `test:unit` package script.

- [x] **Step 4: Run tests and build**

  Run `npm.cmd run test:unit` and expect all tests to pass. Run `npm.cmd run build` and expect Vue TypeScript checking and Vite build to complete successfully.

- [x] **Step 5: Review lifecycle behavior**

  Confirm the timer and visibility listener are removed on unmount, failed loads do not update the timestamp, and the page copy says “每 5 分钟自动刷新” rather than “实时监控”。
