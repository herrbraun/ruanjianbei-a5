import { defineStore } from 'pinia'

import { adminLogin, createGuestSession, getCurrentUser, type AuthResponse, type Role, type UserInfo } from '@/api/auth'

interface AuthState {
  token: string | null
  user: UserInfo | null
  sessionInitialized: boolean
}

let sessionInitialization: Promise<void> | null = null
let guestInitialization: Promise<AuthResponse> | null = null

function clearVisitorSessionReferences() {
  for (let index = localStorage.length - 1; index >= 0; index -= 1) {
    const key = localStorage.key(index)
    if (key?.startsWith('guide_session:')) localStorage.removeItem(key)
  }
}

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
    async ensureGuestSession() {
      if (this.isAuthenticated && this.user?.role === 'visitor') return { access_token: this.token!, token_type: 'bearer' as const, user: this.user }
      if (this.user?.role === 'admin') throw new Error('Administrator session is active')
      if (!guestInitialization) {
        const previousGuestKey = localStorage.getItem('guest_key') || undefined
        guestInitialization = createGuestSession(previousGuestKey)
          .then((response) => {
            if (response.data.guest_key) {
              if (!previousGuestKey || previousGuestKey !== response.data.guest_key) clearVisitorSessionReferences()
              localStorage.setItem('guest_key', response.data.guest_key)
            }
            this.setSession(response.data)
            return response.data
          })
          .finally(() => { guestInitialization = null })
      }
      return guestInitialization
    },
    async recoverGuestSession() {
      this.logout(true)
      const session = await this.ensureGuestSession()
      return session.access_token
    },
    logout(preserveGuestKey = true) {
      this.token = null
      this.user = null
      localStorage.removeItem('auth_token')
      localStorage.removeItem('auth_user')
      if (!preserveGuestKey) localStorage.removeItem('guest_key')
      this.sessionInitialized = true
    },
  },
})
