import { http } from './http'
import { AI_API_TIMEOUT_MS } from './timeouts'

export interface GuideSession {
  id: number
  scenic_area_id: number
  initial_rag_profile_id: number | null
  route_plan_id: number | null
  current_spot_id: number | null
  title: string | null
  created_at: string
  updated_at: string
}

export interface GuideRouteSpot {
  spot_id: number
  sequence: number
  name: string
  summary: string
  stay_minutes: number
  reason: string
  tags: string[]
}

export interface GuideRouteContext {
  route_plan_id: number
  interest: string
  current_spot_id: number
  current_sequence: number
  total_spots: number
  spots: GuideRouteSpot[]
}

export interface GuideSource {
  chunk_id: number
  document_id: number
  knowledge_base_id: number
  knowledge_base_name: string
  source_priority: number
  score: number
  spot_id: string | null
  spot_name: string | null
  section: string | null
  source_locator: string | null
  content: string
}

export interface GuideMessage {
  id: number
  session_id: number
  role: 'user' | 'assistant'
  input_mode: 'text' | 'voice' | null
  content: string
  rag_profile_id: number | null
  sources: GuideSource[] | null
  answer_model: string | null
  answer_duration_ms: number | null
  status: 'success' | 'failed'
  created_at: string
}

export interface GuideConversationResponse {
  visitor_message: GuideMessage
  assistant_message: GuideMessage
  rag_profile_name: string
  knowledge_bases: string[]
}

export interface AsrResult {
  transcript: string
  model: string
  duration_ms: number
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'

export function guideSpeechStreamUrl(messageId: number, avatarVariantId?: number) {
  const query = avatarVariantId ? `?avatar_variant_id=${encodeURIComponent(avatarVariantId)}` : ''
  return `${apiBaseUrl}/guide/messages/${messageId}/speech${query}`
}

export type GuideFeedbackTag = 'answer_accurate' | 'voice_natural' | 'avatar_preferred' | 'slow_response' | 'unresolved'
export interface GuideFeedback { id: number; guide_session_id: number; rating: number; tags: GuideFeedbackTag[]; comment: string | null; created_at: string; updated_at: string }

export const guideApi = {
  createSession: (scenicAreaCode: string, routePlanId?: number, currentSpotId?: number) => http.post<GuideSession>('/guide/sessions', {
    scenic_area_code: scenicAreaCode,
    route_plan_id: routePlanId,
    current_spot_id: currentSpotId,
  }),
  listSessions: () => http.get<GuideSession[]>('/guide/sessions'),
  getSession: (sessionId: number) => http.get<GuideSession>(`/guide/sessions/${sessionId}`),
  getRouteContext: (sessionId: number) => http.get<GuideRouteContext>(`/guide/sessions/${sessionId}/context`),
  updateRouteContext: (sessionId: number, routePlanId: number, currentSpotId: number) => http.patch<GuideRouteContext>(`/guide/sessions/${sessionId}/context`, {
    route_plan_id: routePlanId,
    current_spot_id: currentSpotId,
  }),
  listMessages: (sessionId: number) => http.get<GuideMessage[]>(`/guide/sessions/${sessionId}/messages`),
  getFeedback: (sessionId: number) => http.get<GuideFeedback | null>(`/guide/sessions/${sessionId}/feedback`),
  saveFeedback: (sessionId: number, data: { rating: number; tags: GuideFeedbackTag[]; comment?: string }) => http.post<GuideFeedback>(`/guide/sessions/${sessionId}/feedback`, data),
  sendMessage: (sessionId: number, content: string, inputMode: 'text' | 'voice') =>
    http.post<GuideConversationResponse>(
      `/guide/sessions/${sessionId}/messages`,
      { content, input_mode: inputMode },
      { timeout: AI_API_TIMEOUT_MS },
    ),
  transcribe: (file: Blob) => {
    const form = new FormData()
    form.append('file', file, 'guide-recording.webm')
    return http.post<AsrResult>('/guide/asr', form, { timeout: AI_API_TIMEOUT_MS })
  },
}
