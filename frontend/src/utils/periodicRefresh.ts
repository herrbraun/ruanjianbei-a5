export const AUTO_REFRESH_INTERVAL_MS = 5 * 60 * 1000

export function isPeriodicRefreshDue(lastSuccessfulRefresh: number | undefined, now: number): boolean {
  return lastSuccessfulRefresh === undefined || now - lastSuccessfulRefresh >= AUTO_REFRESH_INTERVAL_MS
}
