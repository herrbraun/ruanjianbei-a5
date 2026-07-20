# Admin Password Change Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow an authenticated administrator to change their own password from the admin layout and force the current tab to log in again.

**Architecture:** Add a dedicated admin-only auth endpoint that reuses existing password verification and hashing. Expose it through the existing frontend auth API and an Element Plus dialog owned by `AppLayout.vue`, so every admin page gets the same desktop and mobile entry without a new route.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, bcrypt/passlib, pytest, Vue 3, TypeScript, Pinia, Element Plus

## Global Constraints

- New administrator passwords must contain 12–64 characters and no more than 72 UTF-8 bytes.
- The new password must differ from the current password.
- Only the current browser tab logs out after success; no database migration or global JWT revocation is added.
- Preserve the existing anonymous visitor flow and all unrelated working-tree changes.

---

### Task 1: Administrator password endpoint

**Files:**
- Modify: `backend/tests/test_auth.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/routers/auth.py`

**Interfaces:**
- Consumes: `verify_password(plain_password, password_hash)`, `update_password(db, user, new_password)`, `require_admin`
- Produces: `POST /api/auth/admin/change-password` with `{current_password, new_password}` and `204 No Content`

- [x] **Step 1: Write failing endpoint tests**

Add tests that log in as `admin`, verify successful change invalidates the old password and accepts the new password, and verify wrong current password, identical password, fewer than 12 characters, and visitor authorization failures.

- [x] **Step 2: Run the focused tests and verify RED**

Run: `cd backend; $env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages'); python -m pytest tests/test_auth.py -q`

Expected: new tests fail because `/api/auth/admin/change-password` does not exist.

- [x] **Step 3: Add the request schema and endpoint**

Create `AdminPasswordChangeRequest` with `current_password: str` and `new_password: str` constrained to 12–64 characters plus the existing 72-byte validator. Add an admin-only route that returns Chinese 400 errors for an incorrect current password or a reused password, calls `update_password`, and returns an empty 204 response.

- [x] **Step 4: Run focused tests and verify GREEN**

Run the Task 1 command again.

Expected: every auth test passes.

### Task 2: Shared administrator dialog

**Files:**
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/layouts/AppLayout.vue`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `changeAdminPassword({current_password, new_password})`
- Produces: desktop and mobile “修改密码” controls and a shared dialog

- [x] **Step 1: Add the typed API wrapper**

Export `changeAdminPassword(payload: { current_password: string; new_password: string })` from `frontend/src/api/auth.ts`.

- [x] **Step 2: Implement dialog state and validation**

In `AppLayout.vue`, add a reactive form with current, new, and confirmation password fields. Require 12–64 characters, confirm equality, prevent reuse client-side, disable duplicate submission, clear values on close, and call the API only for administrators.

- [x] **Step 3: Implement success and failure behavior**

On success, show “密码修改成功，请重新登录”, clear the current session, and `router.replace('/admin/login')`. Preserve backend messages when available and otherwise show a concise failure message.

- [x] **Step 4: Add both layout entry points and focused styling**

Add lock-icon controls beside logout in desktop and mobile account sections. Keep the current visual language and add a compact `.account-actions` flex group without restructuring unrelated layout CSS.

### Task 3: Regression and browser verification

**Files:**
- Verify only; no new production files expected

**Interfaces:**
- Consumes: completed backend endpoint and admin dialog
- Produces: evidence that the complete flow works

- [x] **Step 1: Run full backend tests**

Run: `cd backend; $env:PYTHONPATH=(Join-Path (Get-Location) '.python-packages'); python -m pytest -q`

Expected: all tests pass.

- [x] **Step 2: Run frontend build**

Run: `cd frontend; npm.cmd run build`

Expected: TypeScript checking and Vite build complete successfully.

- [x] **Step 3: Verify in a real browser**

Use an existing administrator session or the configured local administrator credentials to open the dialog and verify the entry, fields, and client-side validation. Do not mutate the developer's real password during browser inspection; the isolated backend endpoint test proves password replacement, old-password rejection, and new-password login without risking an unrecoverable local credential change.

- [x] **Step 4: Inspect final diff**

Run `git diff --check` and `git status --short`; confirm password values, tokens, `.env` files, logs, build output, and unrelated user changes are not staged or overwritten.
