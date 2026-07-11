import { defineStore } from 'pinia'

import { guideApi, type GuideMessage, type GuideSession } from '@/api/guide'

interface GuideState {
  activeSession: GuideSession | null
  activeScenicAreaCode: string | null
  messages: GuideMessage[]
  loadingMessages: boolean
  sending: boolean
}

function storageKey(scenicAreaCode: string) {
  return `guide_session:${scenicAreaCode}`
}

export const useGuideStore = defineStore('guide', {
  state: (): GuideState => ({
    activeSession: null,
    activeScenicAreaCode: null,
    messages: [],
    loadingMessages: false,
    sending: false,
  }),
  actions: {
    async openScenicArea(scenicAreaCode: string) {
      this.activeScenicAreaCode = scenicAreaCode
      this.messages = []
      this.activeSession = null
      this.loadingMessages = true
      try {
        const storedSessionId = Number(localStorage.getItem(storageKey(scenicAreaCode)))
        if (Number.isInteger(storedSessionId) && storedSessionId > 0) {
          try {
            const messages = await guideApi.listMessages(storedSessionId)
            this.activeSession = { id: storedSessionId } as GuideSession
            this.messages = messages.data
            return
          } catch {
            localStorage.removeItem(storageKey(scenicAreaCode))
          }
        }
        const response = await guideApi.createSession(scenicAreaCode)
        this.activeSession = response.data
        localStorage.setItem(storageKey(scenicAreaCode), String(response.data.id))
      } finally {
        this.loadingMessages = false
      }
    },
    async send(content: string, inputMode: 'text' | 'voice') {
      if (!this.activeSession) throw new Error('Guide session is not ready')
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
