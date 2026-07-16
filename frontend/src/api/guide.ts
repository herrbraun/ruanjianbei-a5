import { http } from './http'
import { AI_API_TIMEOUT_MS } from './timeouts'

export interface GuideSession {
  id: number
  scenic_area_id: number
  initial_rag_profile_id: number | null
  title: string | null
  created_at: string
  updated_at: string
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

export type GuideFeedbackTag = 'answer_accurate' | 'voice_natural' | 'avatar_preferred' | 'slow_response' | 'unresolved'
export interface GuideFeedback { id: number; guide_session_id: number; rating: number; tags: GuideFeedbackTag[]; comment: string | null; created_at: string; updated_at: string }

export const guideApi = {
  createSession: (scenicAreaCode: string) => http.post<GuideSession>('/guide/sessions', { scenic_area_code: scenicAreaCode }),
  listSessions: () => http.get<GuideSession[]>('/guide/sessions'),
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
  synthesize: (messageId: number, avatarVariantId?: number) =>
    http.post<Blob>(`/guide/messages/${messageId}/speech`, undefined, {
      params: avatarVariantId ? { avatar_variant_id: avatarVariantId } : undefined,
      responseType: 'blob',
      timeout: AI_API_TIMEOUT_MS,
    }),
}
