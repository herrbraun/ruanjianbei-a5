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
}

export interface AuthResponse {
  access_token: string
  token_type: 'bearer'
  user: UserInfo
}

export interface UsernameAvailability {
  available: boolean
  suggestions: string[]
}

export interface UsernameConflictDetail {
  code: 'username_taken'
  message: string
  suggestions: string[]
}

export function visitorRegister(payload: { username: string; password: string }) {
  return http.post<AuthResponse>('/auth/visitor-register', payload)
}

export function visitorLogin(payload: { username: string; password: string }) {
  return http.post<AuthResponse>('/auth/visitor-login', payload)
}

export function adminLogin(payload: { username: string; password: string }) {
  return http.post<AuthResponse>('/auth/admin-login', payload)
}

export function checkUsernameAvailability(username: string) {
  return http.get<UsernameAvailability>('/auth/username-availability', { params: { username } })
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

export function changePassword(payload: { current_password: string; new_password: string }) {
  return http.post<void>('/auth/change-password', payload)
}

export function uploadAvatar(file: File) {
  const data = new FormData()
  data.append('file', file)
  return http.post<UserInfo>('/auth/avatar', data)
}

export function resolveAssetUrl(path: string | null | undefined) {
  if (!path) return null
  if (/^https?:\/\//i.test(path)) return path
  const baseUrl = http.defaults.baseURL || 'http://localhost:8000/api'
  const origin = /^https?:\/\//i.test(baseUrl) ? new URL(baseUrl).origin : window.location.origin
  return `${origin}${path.startsWith('/') ? path : `/${path}`}`
}
