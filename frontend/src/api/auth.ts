import { http } from './http'

export type Role = 'visitor' | 'admin'

export interface UserInfo {
  id: number
  role: Role
  username: string | null
  nickname: string | null
  avatar_url: string | null
  interest: string | null
  interests: string[]
  needs_interest_setup: boolean
  is_guest: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: 'bearer'
  user: UserInfo
}

export interface GuestAuthResponse extends AuthResponse {
  guest_key: string | null
}

export function createGuestSession(guestKey?: string) {
  return http.post<GuestAuthResponse>('/auth/guest-session', { guest_key: guestKey })
}

export function adminLogin(payload: { username: string; password: string }) {
  return http.post<AuthResponse>('/auth/admin-login', payload)
}

export function getInterestOptions() {
  return http.get<{ interests: string[] }>('/auth/interests')
}

export function getCurrentUser() {
  return http.get<UserInfo>('/auth/me')
}

export function updateProfile(payload: { nickname?: string; interests?: string[] }) {
  return http.patch<UserInfo>('/auth/me', payload)
}

export function resolveAssetUrl(path: string | null | undefined) {
  if (!path) return null
  if (/^https?:\/\//i.test(path)) return path
  const baseUrl = http.defaults.baseURL || 'http://localhost:8000/api'
  const origin = /^https?:\/\//i.test(baseUrl) ? new URL(baseUrl).origin : window.location.origin
  return `${origin}${path.startsWith('/') ? path : `/${path}`}`
}
