import { defineStore } from 'pinia'

import { adminLogin, getCurrentUser, type AuthResponse, type Role, type UserInfo, visitorLogin } from '@/api/auth'

interface AuthState {
  token: string | null
  user: UserInfo | null
  sessionInitialized: boolean
}

let sessionInitialization: Promise<void> | null = null

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem('auth_token'),
    user: null,
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
      this.sessionInitialized = true
      localStorage.setItem('auth_token', payload.access_token)
    },
    async loginVisitor(payload: { nickname: string; interest?: string }) {
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
      this.user = response.data
    },
    async initializeSession() {
      if (this.sessionInitialized) {
        return
      }

      if (sessionInitialization) {
        return sessionInitialization
      }

      sessionInitialization = (async () => {
        try {
          if (this.token) {
            await this.refreshCurrentUser()
          } else {
            this.user = null
            localStorage.removeItem('auth_user')
          }
        } catch {
          this.logout()
        } finally {
          this.sessionInitialized = true
        }
      })()

      try {
        await sessionInitialization
      } finally {
        sessionInitialization = null
      }
    },
    logout() {
      this.token = null
      this.user = null
      this.sessionInitialized = true
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
    },
  },
})
