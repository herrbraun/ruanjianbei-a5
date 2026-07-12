import { defineStore } from 'pinia'

import { adminLogin, getCurrentUser, type AuthResponse, type Role, type UserInfo, visitorLogin, visitorRegister } from '@/api/auth'

interface AuthState {
  token: string | null
  user: UserInfo | null
  sessionInitialized: boolean
}

let sessionInitialization: Promise<void> | null = null

function readStoredUser(): UserInfo | null {
  const raw = localStorage.getItem('auth_user')
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as UserInfo
  } catch {
    localStorage.removeItem('auth_user')
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem('auth_token'),
    user: readStoredUser(),
    sessionInitialized: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    role: (state): Role | null => state.user?.role ?? null,
  },
  actions: {
    setSession(payload: AuthResponse) {
      this.token = payload.access_token
      this.user = payload.user
      localStorage.setItem('auth_token', payload.access_token)
      localStorage.setItem('auth_user', JSON.stringify(payload.user))
      this.sessionInitialized = true
    },
    setUser(user: UserInfo) {
      this.user = user
      localStorage.setItem('auth_user', JSON.stringify(user))
    },
    async registerVisitor(payload: { username: string; password: string }) {
      const response = await visitorRegister(payload)
      this.setSession(response.data)
    },
    async loginVisitor(payload: { username: string; password: string }) {
      const response = await visitorLogin(payload)
      this.setSession(response.data)
    },
    async loginAdmin(payload: { username: string; password: string }) {
      const response = await adminLogin(payload)
      this.setSession(response.data)
    },
    async refreshCurrentUser() {
      if (!this.token) {
        return
      }
      const response = await getCurrentUser()
      this.setUser(response.data)
    },
    async initializeSession() {
      if (this.sessionInitialized) return
      if (!this.token) {
        this.logout()
        return
      }
      if (!sessionInitialization) {
        sessionInitialization = this.refreshCurrentUser()
          .catch(() => this.logout())
          .finally(() => {
            this.sessionInitialized = true
            sessionInitialization = null
          })
      }
      await sessionInitialization
    },
    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
      this.sessionInitialized = true
    },
  },
})
