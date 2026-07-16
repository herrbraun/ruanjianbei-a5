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

export function getAnalyticsOverview() {
  return http.get<AnalyticsOverview>('/admin/analytics/overview')
}

export function getRouteAnalytics() {
  return http.get<RouteAnalytics>('/admin/analytics/routes')
}

export function getSpotAnalytics() {
  return http.get<SpotAnalytics>('/admin/analytics/spots')
}
