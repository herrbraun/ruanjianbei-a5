import assert from 'node:assert/strict'
import test from 'node:test'

import {
  AUTO_REFRESH_INTERVAL_MS,
  isPeriodicRefreshDue,
} from '../src/utils/periodicRefresh.ts'

test('没有成功刷新记录时需要刷新', () => {
  assert.equal(isPeriodicRefreshDue(undefined, 1_000), true)
})

test('距离上次成功刷新不足五分钟时不刷新', () => {
  assert.equal(isPeriodicRefreshDue(1_000, 1_000 + AUTO_REFRESH_INTERVAL_MS - 1), false)
})

test('距离上次成功刷新达到五分钟时刷新', () => {
  assert.equal(isPeriodicRefreshDue(1_000, 1_000 + AUTO_REFRESH_INTERVAL_MS), true)
})
