import axios, { type InternalAxiosRequestConfig } from 'axios'

import { DEFAULT_API_TIMEOUT_MS } from './timeouts'

type RetryableRequestConfig = InternalAxiosRequestConfig & { _guestRetried?: boolean }
type UnauthorizedHandler = () => Promise<string | null> | string | null

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
let unauthorizedHandler: UnauthorizedHandler | null = null

export function setUnauthorizedHandler(handler: UnauthorizedHandler) {
  unauthorizedHandler = handler
}

export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_API_TIMEOUT_MS,
})

http.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const detail = axios.isAxiosError(error) ? error.response?.data?.detail : undefined
    const roleMismatch = error.response?.status === 403 && (
      detail === 'Visitor role required'
      || detail === 'Visitor permission required'
      || detail === 'Admin role required'
    )
    if (axios.isAxiosError(error) && (error.response?.status === 401 || roleMismatch) && error.config) {
      const config = error.config as RetryableRequestConfig
      if (!config._guestRetried && unauthorizedHandler) {
        config._guestRetried = true
        const replacementToken = await unauthorizedHandler()
        if (replacementToken) {
          config.headers.Authorization = `Bearer ${replacementToken}`
          return http.request(config)
        }
      }
    }
    return Promise.reject(error)
  },
)
