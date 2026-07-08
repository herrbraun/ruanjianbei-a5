import { http } from './http'

export type Role = 'visitor' | 'admin'

export interface UserInfo {
  id: number
  role: Role
  username: string | null
  nickname: string | null
  interest: string | null
}

export interface AuthResponse {
  access_token: string
  token_type: 'bearer'
  user: UserInfo
}

export function visitorLogin(payload: { nickname: string; interest?: string }) {
  return http.post<AuthResponse>('/auth/visitor-login', payload)
}

export function adminLogin(payload: { username: string; password: string }) {
  return http.post<AuthResponse>('/auth/admin-login', payload)
}

export function getCurrentUser() {
  return http.get<UserInfo>('/auth/me')
}
