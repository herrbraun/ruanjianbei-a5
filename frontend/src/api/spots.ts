import { http } from './http'

export type SpotStatus = 'enabled' | 'disabled'
export type SpotType = 'attraction' | 'area' | 'service'
export type MediaType = 'image' | 'video' | 'audio'

export interface SpotMediaAsset {
  id: number
  spot_id: number
  spot_name: string | null
  media_type: MediaType
  url: string
  description: string | null
  sort_order: number
  status: SpotStatus
  created_at: string
  updated_at: string
}

export interface ScenicSpot {
  id: number
  external_id: string | null
  scenic_area: string
  spot_type: SpotType
  name: string
  summary: string
  description: string
  location: string | null
  opening_hours: string | null
  landscape_parameters: string | null
  cultural_context: string | null
  highlights: string | null
  notes: string | null
  source_name: string | null
  recommended_duration_minutes: number
  priority: number
  status: SpotStatus
  cover_image_url: string | null
  tags: string[]
  media_assets: SpotMediaAsset[]
  created_at: string
  updated_at: string
}

export interface SpotPayload {
  external_id?: string | null
  scenic_area: string
  spot_type: SpotType
  name: string
  summary: string
  description: string
  location?: string | null
  opening_hours?: string | null
  landscape_parameters?: string | null
  cultural_context?: string | null
  highlights?: string | null
  notes?: string | null
  source_name?: string | null
  recommended_duration_minutes: number
  priority: number
  status: SpotStatus
  cover_image_url?: string | null
  tags: string[]
}

export interface MediaPayload {
  spot_id: number
  media_type: MediaType
  url: string
  description?: string | null
  sort_order: number
  status: SpotStatus
}

export function getSpots(params?: { tag?: string; keyword?: string; scenic_area?: string; spot_type?: SpotType }) {
  return http.get<ScenicSpot[]>('/spots', { params })
}

export function getSpot(id: number) {
  return http.get<ScenicSpot>(`/spots/${id}`)
}

export function getAdminSpots(params?: { scenic_area?: string; spot_type?: SpotType }) {
  return http.get<ScenicSpot[]>('/admin/spots', { params })
}

export function createAdminSpot(payload: SpotPayload) {
  return http.post<ScenicSpot>('/admin/spots', payload)
}

export function updateAdminSpot(id: number, payload: SpotPayload) {
  return http.put<ScenicSpot>(`/admin/spots/${id}`, payload)
}

export function updateAdminSpotStatus(id: number, status: SpotStatus) {
  return http.patch<ScenicSpot>(`/admin/spots/${id}/status`, { status })
}

export function getAdminMedia(spotId?: number) {
  return http.get<SpotMediaAsset[]>('/admin/media', { params: { spot_id: spotId } })
}

export function createAdminMedia(payload: MediaPayload) {
  return http.post<SpotMediaAsset>('/admin/media', payload)
}

export function updateAdminMedia(id: number, payload: MediaPayload) {
  return http.put<SpotMediaAsset>(`/admin/media/${id}`, payload)
}

export function deleteAdminMedia(id: number) {
  return http.delete(`/admin/media/${id}`)
}
