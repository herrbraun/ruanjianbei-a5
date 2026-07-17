import { defineStore } from 'pinia'

import { guideApi, type GuideMessage, type GuideRouteContext, type GuideSession } from '@/api/guide'

interface GuideState {
  activeSession: GuideSession | null
  activeScenicAreaCode: string | null
  activeRouteContext: GuideRouteContext | null
  messages: GuideMessage[]
  loadingMessages: boolean
  sending: boolean
  updatingRouteContext: boolean
}

function storageKey(scenicAreaCode: string, routePlanId?: number) {
  return routePlanId
    ? `guide_session:${scenicAreaCode}:route:${routePlanId}`
    : `guide_session:${scenicAreaCode}`
}

export const useGuideStore = defineStore('guide', {
  state: (): GuideState => ({
    activeSession: null,
    activeScenicAreaCode: null,
    activeRouteContext: null,
    messages: [],
    loadingMessages: false,
    sending: false,
    updatingRouteContext: false,
  }),
  actions: {
    async openScenicArea(scenicAreaCode: string, routePlanId?: number, currentSpotId?: number) {
      this.activeScenicAreaCode = scenicAreaCode
      this.messages = []
      this.activeSession = null
      this.activeRouteContext = null
      this.loadingMessages = true
      try {
        const activeStorageKey = storageKey(scenicAreaCode, routePlanId)
        const storedSessionId = Number(localStorage.getItem(activeStorageKey))
        if (Number.isInteger(storedSessionId) && storedSessionId > 0) {
          try {
            const [session, messages] = await Promise.all([
              guideApi.getSession(storedSessionId),
              guideApi.listMessages(storedSessionId),
            ])
            const sessionMatchesContext = routePlanId
              ? session.data.route_plan_id === routePlanId
              : session.data.route_plan_id === null
            if (sessionMatchesContext) {
              this.activeSession = session.data
              this.messages = messages.data
            } else {
              localStorage.removeItem(activeStorageKey)
            }
          } catch {
            localStorage.removeItem(activeStorageKey)
          }
        }
        if (!this.activeSession) {
          const response = await guideApi.createSession(scenicAreaCode, routePlanId, currentSpotId)
          this.activeSession = response.data
          localStorage.setItem(activeStorageKey, String(response.data.id))
        }
        if (routePlanId && currentSpotId) {
          this.activeRouteContext = this.activeSession.route_plan_id === routePlanId && this.activeSession.current_spot_id === currentSpotId
            ? (await guideApi.getRouteContext(this.activeSession.id)).data
            : (await guideApi.updateRouteContext(this.activeSession.id, routePlanId, currentSpotId)).data
          this.activeSession.route_plan_id = routePlanId
          this.activeSession.current_spot_id = currentSpotId
        } else if (this.activeSession.route_plan_id && this.activeSession.current_spot_id) {
          try {
            this.activeRouteContext = (await guideApi.getRouteContext(this.activeSession.id)).data
          } catch {
            this.activeRouteContext = null
          }
        }
      } finally {
        this.loadingMessages = false
      }
    },
    async setRouteStop(routePlanId: number, currentSpotId: number) {
      if (!this.activeSession) throw new Error('Guide session is not ready')
      if (this.updatingRouteContext) throw new Error('Route context update is already in progress')
      this.updatingRouteContext = true
      try {
        this.activeRouteContext = (await guideApi.updateRouteContext(this.activeSession.id, routePlanId, currentSpotId)).data
        this.activeSession.route_plan_id = routePlanId
        this.activeSession.current_spot_id = currentSpotId
        return this.activeRouteContext
      } finally {
        this.updatingRouteContext = false
      }
    },
    closeActiveGuide() {
      this.activeSession = null
      this.activeScenicAreaCode = null
      this.activeRouteContext = null
      this.messages = []
      this.loadingMessages = false
      this.sending = false
      this.updatingRouteContext = false
    },
    async send(content: string, inputMode: 'text' | 'voice') {
      if (!this.activeSession) throw new Error('Guide session is not ready')
      if (this.sending) throw new Error('Guide request is already in progress')
      this.sending = true
      try {
        const response = await guideApi.sendMessage(this.activeSession.id, content, inputMode)
        this.messages.push(response.data.visitor_message, response.data.assistant_message)
        return response.data
      } finally {
        this.sending = false
      }
    },
  },
})
