import { http } from './http'

export type RoutePreference = 'balanced' | 'priority' | 'more_spots'

export interface RouteSpot {
  id: number
  spot_id: number | null
  sequence: number
  name: string
  summary: string
  location: string | null
  cover_image_url: string | null
  stay_minutes: number
  reason: string
  tags: string[]
}

export interface RoutePlan {
  id: number
  interest: string
  start_spot_id: number | null
  preference: RoutePreference
  duration_minutes: number
  total_duration_minutes: number
  reason: string
  created_at: string
  spots: RouteSpot[]
}

export interface RouteFeedback {
  id: number
  route_plan_id: number
  rating: number
  comment: string | null
  created_at: string
}

export interface AdminRoute {
  id: number
  user_id: number | null
  visitor_name: string | null
  interest: string
  start_spot_id: number | null
  preference: RoutePreference
  duration_minutes: number
  total_duration_minutes: number
  spot_count: number
  rating: number | null
  comment: string | null
  created_at: string
}

export interface RouteSettings {
  tag_match_weight: number
  priority_weight: number
  max_spots: number
  include_service_points: boolean
  updated_at?: string | null
}

export function recommendRoute(payload: {
  interest: string
  duration_minutes: number
  start_spot_id?: number
  preference: RoutePreference
}) {
  return http.post<RoutePlan>('/routes/recommend', payload)
}

export function getRoute(id: number) {
  return http.get<RoutePlan>(`/routes/${id}`)
}

export function submitRouteFeedback(id: number, payload: { rating: number; comment?: string }) {
  return http.post<RouteFeedback>(`/routes/${id}/feedback`, payload)
}

export function getAdminRoutes(params?: { interest?: string; rating?: number }) {
  return http.get<AdminRoute[]>('/admin/routes', { params })
}

export function getRouteSettings() {
  return http.get<RouteSettings>('/admin/routes/settings')
}

export function updateRouteSettings(payload: RouteSettings) {
  return http.put<RouteSettings>('/admin/routes/settings', payload)
}
