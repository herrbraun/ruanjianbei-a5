import { http } from './http'

export interface AnalyticsOverview {
  login_count: number
  spot_count: number
  enabled_spot_count: number
  media_count: number
  route_count: number
  feedback_count: number
  average_rating: number | null
  behavior_record_count: number
  behavior_visitor_count: number
  behavior_average_satisfaction: number | null
}

export interface RouteAnalytics {
  total_routes: number
  feedback_rate: number
  average_requested_minutes: number | null
  average_planned_minutes: number | null
  daily_routes: Array<{ date: string; count: number }>
  popular_interests: Array<{ name: string; count: number }>
  rating_distribution: Array<{ rating: number; count: number }>
}

export interface SpotAnalytics {
  route_popular_spots: Array<{ spot_id: number; name: string; scenic_area: string; selected_count: number }>
  behavior_attractions: Array<{
    name: string
    visits: number
    unique_visitors: number
    average_stay_hours: number
    average_cost: number
    average_satisfaction: number
  }>
}

export interface GuideDashboardMetrics {
  service_visitors: number; session_count: number; question_count: number; answer_success_rate: number
  average_answer_duration_ms: number | null; average_rating: number | null; negative_rate: number
  analysis_coverage_rate: number; analysis_failed_count: number
}
export interface GuideDashboard {
  period: { start_date: string; end_date: string }
  metrics: GuideDashboardMetrics
  previous_period: GuideDashboardMetrics
  service_trend: Array<{ date: string; sessions: number; visitors: number }>
  sentiment_trend: Array<{ date: string; positive: number; neutral: number; negative: number }>
  satisfaction_trend: Array<{ date: string; average_rating: number; count: number }>
  topic_distribution: Array<{ name: string; count: number }>
  popular_questions: Array<{ name: string; count: number }>
  attention_preview: Array<{ id: number; normalized_question: string | null; issue_type: string | null; sentiment: string | null; created_at: string }>
}

export function getAnalyticsOverview() {
  return http.get<AnalyticsOverview>('/admin/analytics/overview')
}

export function getRouteAnalytics() {
  return http.get<RouteAnalytics>('/admin/analytics/routes')
}

export function getSpotAnalytics() {
  return http.get<SpotAnalytics>('/admin/analytics/spots')
}

export function getGuideDashboard(scenicAreaId: number, startDate: string, endDate: string) {
  return http.get<GuideDashboard>('/admin/analytics/guide', { params: { scenic_area_id: scenicAreaId, start_date: startDate, end_date: endDate } })
}
